import csv
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from .forms import DocumentForm, MoveForm, OCRConfirmForm, RussianLoginForm, TrainForm, WagonForm
from .models import Document, MovementHistory, Notification, OperationLog, RailwayTrack, Role, TrackSection, Train, Wagon
from .services import confirm_ocr, log_action, move_object, notify, refresh_section_occupancy, run_ocr


def role_required(*roles):
    def check(user):
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return getattr(getattr(user, 'profile', None), 'role', None) and user.profile.role.name in roles
    return user_passes_test(check, login_url='/login/')


class LoginView(auth_views.LoginView):
    template_name = 'rail/login.html'
    authentication_form = RussianLoginForm

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action(self.request.user, 'Вход пользователя', description='Успешный вход в систему')
        return response


@login_required
def dashboard(request):
    refresh_section_occupancy()
    context = {
        'active_trains': Train.objects.exclude(status=Train.DEPARTED).count(),
        'wagons': Wagon.objects.exclude(status='departed').count(),
        'occupied_sections': TrackSection.objects.filter(is_occupied=True).count(),
        'unplaced_trains': Train.objects.filter(current_section__isnull=True).exclude(status=Train.DEPARTED).count(),
        'pending_docs': Document.objects.exclude(ocr_status='confirmed').count(),
        'logs': OperationLog.objects.select_related('user')[:8],
    }
    return render(request, 'rail/dashboard.html', context)


class FilteredListMixin:
    paginate_by = 10
    search_fields = []

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get('q', '')
        if q and self.search_fields:
            query = Q()
            for field in self.search_fields:
                query |= Q(**{f'{field}__icontains': q})
            qs = qs.filter(query)
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        track = self.request.GET.get('track')
        if track:
            qs = qs.filter(current_track_id=track)
        return qs

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        data['tracks'] = RailwayTrack.objects.all()
        data['q'] = self.request.GET.get('q', '')
        return data


class TrainList(LoginRequiredMixin, FilteredListMixin, ListView):
    model = Train
    template_name = 'rail/train_list.html'
    search_fields = ['train_number', 'cargo_type']


class TrainCreate(LoginRequiredMixin, CreateView):
    model = Train
    form_class = TrainForm
    template_name = 'rail/form.html'
    success_url = reverse_lazy('trains')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        log_action(self.request.user, 'Создание состава', self.object, f'Создан состав {self.object.train_number}')
        if not self.object.current_section:
            notify(self.request.user, 'Состав не размещен', f'Состав {self.object.train_number} ожидает размещения', 'warning')
        return response


class TrainDetail(LoginRequiredMixin, DetailView):
    model = Train
    template_name = 'rail/train_detail.html'


class TrainUpdate(LoginRequiredMixin, UpdateView):
    model = Train
    form_class = TrainForm
    template_name = 'rail/form.html'

    def get_success_url(self):
        return self.object.get_absolute_url() if hasattr(self.object, 'get_absolute_url') else f'/trains/{self.object.id}/'

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action(self.request.user, 'Изменение состава', self.object, f'Изменен состав {self.object.train_number}')
        return response


@login_required
def depart_train(request, pk):
    train = get_object_or_404(Train, pk=pk)
    train.status = Train.DEPARTED
    train.departure_datetime = timezone.now()
    train.save()
    train.wagons.update(status='departed', departure_datetime=timezone.now())
    refresh_section_occupancy()
    log_action(request.user, 'Отправление состава', train, f'Состав {train.train_number} отправлен')
    messages.success(request, 'Состав отмечен как отправленный')
    return redirect('train_detail', pk=pk)


class WagonList(LoginRequiredMixin, FilteredListMixin, ListView):
    model = Wagon
    template_name = 'rail/wagon_list.html'
    search_fields = ['wagon_number', 'cargo_type', 'cargo_description']


class WagonCreate(LoginRequiredMixin, CreateView):
    model = Wagon
    form_class = WagonForm
    template_name = 'rail/form.html'
    success_url = reverse_lazy('wagons')

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action(self.request.user, 'Добавление вагона', self.object, f'Добавлен вагон {self.object.wagon_number}')
        return response


class WagonDetail(LoginRequiredMixin, DetailView):
    model = Wagon
    template_name = 'rail/wagon_detail.html'


class WagonUpdate(LoginRequiredMixin, UpdateView):
    model = Wagon
    form_class = WagonForm
    template_name = 'rail/form.html'

    def get_success_url(self):
        return f'/wagons/{self.object.id}/'

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action(self.request.user, 'Изменение вагона', self.object, f'Обновлен вагон {self.object.wagon_number}')
        return response


@login_required
def tracks(request):
    return render(request, 'rail/tracks.html', {'tracks': RailwayTrack.objects.prefetch_related('sections')})


@role_required(Role.ADMIN, Role.DISPATCHER)
def track_map(request):
    if request.method == 'POST':
        form = MoveForm(request.POST)
        if form.is_valid():
            target = form.cleaned_data['train'] if form.cleaned_data['target_type'] == 'train' else form.cleaned_data['wagon']
            if not target:
                messages.error(request, 'Выберите объект для перемещения')
            else:
                try:
                    move_object(user=request.user, target=target, section=form.cleaned_data['section'], comment=form.cleaned_data['comment'])
                    messages.success(request, 'Перемещение сохранено')
                except ValueError as exc:
                    messages.error(request, str(exc))
            return redirect('track_map')
    else:
        form = MoveForm()
    return render(request, 'rail/track_map.html', {'tracks': RailwayTrack.objects.prefetch_related('sections'), 'trains': Train.objects.exclude(status=Train.DEPARTED), 'wagons': Wagon.objects.exclude(status='departed'), 'form': form})


@role_required(Role.ADMIN, Role.DISPATCHER)
@require_POST
def track_map_drag_wagon(request):
    wagon = get_object_or_404(Wagon, pk=request.POST.get('wagon_id'))
    section = get_object_or_404(TrackSection, pk=request.POST.get('section_id'))
    if wagon.current_section_id == section.id:
        return JsonResponse({'ok': True, 'message': 'Вагон уже находится на этом участке'})
    try:
        move_object(user=request.user, target=wagon, section=section, comment='Перемещение вагона мышкой на схеме путей')
    except ValueError as exc:
        return JsonResponse({'ok': False, 'message': str(exc)}, status=400)
    return JsonResponse({'ok': True, 'message': f'Вагон {wagon.wagon_number} перемещен на участок {section}'})


@login_required
def documents(request):
    return render(request, 'rail/documents.html', {'documents': Document.objects.select_related('train')})


@login_required
def upload_document(request):
    form = DocumentForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        doc = form.save(commit=False)
        doc.uploaded_by = request.user
        doc.save()
        log_action(request.user, 'Загрузка документа', doc, f'Загружен документ к составу {doc.train}')
        notify(request.user, 'Документ ожидает OCR', f'Документ {doc.id} загружен, запустите распознавание', 'info')
        return redirect('documents')
    return render(request, 'rail/form.html', {'form': form, 'title': 'Загрузка документа'})


@login_required
def document_ocr(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    if request.method == 'POST' and 'run' in request.POST:
        try:
            result = run_ocr(doc)
            log_action(request.user, 'Запуск OCR', doc, f'OCR документа {doc.id}')
            messages.success(request, 'OCR выполнен, проверьте результат')
        except Exception as exc:
            doc.ocr_status = 'error'
            doc.recognized_text = str(exc)
            doc.save(update_fields=['ocr_status', 'recognized_text'])
            notify(request.user, 'Ошибка OCR', str(exc), 'error')
            messages.error(request, f'OCR недоступен: {exc}')
        return redirect('document_ocr', pk=pk)
    result = getattr(doc, 'ocr_result', None)
    form = OCRConfirmForm(request.POST or None, instance=result)
    if request.method == 'POST' and 'confirm' in request.POST and form.is_valid():
        result = form.save(commit=False)
        result.document = doc
        result.save()
        confirm_ocr(result, request.user)
        messages.success(request, 'Результат OCR подтвержден')
        return redirect('documents')
    return render(request, 'rail/document_ocr.html', {'document': doc, 'form': form, 'result': result})


@login_required
def reports(request):
    trains = Train.objects.all()
    wagons = Wagon.objects.all()
    movements = MovementHistory.objects.select_related('train', 'wagon', 'to_track', 'to_section')[:50]
    status_labels = dict(Wagon.STATUS_CHOICES)
    wagon_statuses = [
        {'status': status_labels.get(row['status'], row['status']), 'total': row['total']}
        for row in wagons.values('status').annotate(total=Count('id'))
    ]
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="rail_report.csv"'
        writer = csv.writer(response)
        writer.writerow(['Тип', 'Номер', 'Статус', 'Путь', 'Участок'])
        for train in trains:
            writer.writerow(['Состав', train.train_number, train.get_status_display(), train.current_track or '', train.current_section or ''])
        for wagon in wagons:
            writer.writerow(['Вагон', wagon.wagon_number, wagon.get_status_display(), wagon.current_track or '', wagon.current_section or ''])
        log_action(request.user, 'Формирование отчета', description='Экспорт CSV')
        return response
    return render(request, 'rail/reports.html', {'trains': trains[:20], 'wagons': wagons[:20], 'movements': movements, 'wagon_statuses': wagon_statuses})


@login_required
def notifications(request):
    if request.method == 'POST':
        request.user.notifications.update(is_read=True)
        return redirect('notifications')
    return render(request, 'rail/notifications.html', {'notifications': request.user.notifications.all()})


@role_required(Role.ADMIN)
def admin_panel(request):
    return render(request, 'rail/admin_panel.html', {'logs': OperationLog.objects.select_related('user')[:100], 'users_count': User.objects.count()})
