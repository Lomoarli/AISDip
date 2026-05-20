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
from django.utils.decorators import method_decorator
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


def _sync_train_wagons(train):
    existing = {w.wagon_number: w for w in train.wagons.all()}
    for idx in range(1, train.wagon_count + 1):
        number = f'{train.train_number}-{idx}'
        wagon = existing.pop(number, None)
        if wagon is None:
            Wagon.objects.create(
                wagon_number=number,
                train=train,
                cargo_type=train.cargo_type,
                cargo_description=f'Автосоздан для состава {train.train_number}',
                status='arrived',
                current_track=train.current_track,
                current_section=train.current_section,
                arrival_datetime=train.arrival_datetime,
                departure_datetime=train.departure_datetime,
            )
        else:
            wagon.train = train
            wagon.cargo_type = train.cargo_type
            wagon.current_track = train.current_track
            wagon.current_section = train.current_section
            wagon.arrival_datetime = train.arrival_datetime
            wagon.departure_datetime = train.departure_datetime
            wagon.save()
    for wagon in existing.values():
        wagon.train = train
        wagon.status = 'departed'
        wagon.departure_datetime = train.departure_datetime or timezone.now()
        wagon.save()


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


@method_decorator(role_required(Role.ADMIN, Role.OPERATOR, Role.DISPATCHER), name='dispatch')
class TrainList(LoginRequiredMixin, FilteredListMixin, ListView):
    model = Train
    template_name = 'rail/train_list.html'
    search_fields = ['train_number', 'cargo_type']


@method_decorator(role_required(Role.ADMIN, Role.OPERATOR), name='dispatch')
class TrainCreate(LoginRequiredMixin, CreateView):
    model = Train
    form_class = TrainForm
    template_name = 'rail/form.html'
    success_url = reverse_lazy('trains')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        log_action(self.request.user, 'Создание состава', self.object, f'Создан состав {self.object.train_number}')
        _sync_train_wagons(self.object)
        if not self.object.current_section:
            notify(self.request.user, 'Состав не размещен', f'Состав {self.object.train_number} ожидает размещения', 'warning')
        return response


@method_decorator(role_required(Role.ADMIN, Role.OPERATOR, Role.DISPATCHER), name='dispatch')
class TrainDetail(LoginRequiredMixin, DetailView):
    model = Train
    template_name = 'rail/train_detail.html'


@method_decorator(role_required(Role.ADMIN, Role.OPERATOR), name='dispatch')
class TrainUpdate(LoginRequiredMixin, UpdateView):
    model = Train
    form_class = TrainForm
    template_name = 'rail/form.html'

    def get_success_url(self):
        return self.object.get_absolute_url() if hasattr(self.object, 'get_absolute_url') else f'/trains/{self.object.id}/'

    def form_valid(self, form):
        response = super().form_valid(form)
        _sync_train_wagons(self.object)
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


@method_decorator(role_required(Role.ADMIN, Role.OPERATOR, Role.DISPATCHER), name='dispatch')
class WagonList(LoginRequiredMixin, FilteredListMixin, ListView):
    model = Wagon
    template_name = 'rail/wagon_list.html'
    search_fields = ['wagon_number', 'cargo_type', 'cargo_description']


@method_decorator(role_required(Role.ADMIN, Role.OPERATOR), name='dispatch')
class WagonCreate(LoginRequiredMixin, CreateView):
    model = Wagon
    form_class = WagonForm
    template_name = 'rail/form.html'
    success_url = reverse_lazy('wagons')

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action(self.request.user, 'Добавление вагона', self.object, f'Добавлен вагон {self.object.wagon_number}')
        return response


@method_decorator(role_required(Role.ADMIN, Role.OPERATOR, Role.DISPATCHER), name='dispatch')
class WagonDetail(LoginRequiredMixin, DetailView):
    model = Wagon
    template_name = 'rail/wagon_detail.html'


@method_decorator(role_required(Role.ADMIN, Role.OPERATOR), name='dispatch')
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


@role_required(Role.ADMIN, Role.OPERATOR, Role.DISPATCHER)
def tracks(request):
    return render(request, 'rail/tracks.html', {'tracks': RailwayTrack.objects.prefetch_related('sections')})


@role_required(Role.ADMIN, Role.DISPATCHER)
def track_map(request):
    if request.method == 'POST':
        form = MoveForm(request.POST)
        if form.is_valid():
            try:
                move_object(user=request.user, target=form.get_target(), section=form.cleaned_data['section'], comment=form.cleaned_data['comment'])
                messages.success(request, 'Перемещение сохранено')
            except ValueError as exc:
                messages.error(request, str(exc))
            return redirect('track_map')
    else:
        form = MoveForm()
    return render(request, 'rail/track_map.html', {'tracks': RailwayTrack.objects.prefetch_related('sections'), 'trains': Train.objects.exclude(status=Train.DEPARTED), 'wagons': Wagon.objects.exclude(status='departed'), 'form': form})


@role_required(Role.ADMIN, Role.DISPATCHER)
@require_POST
def track_map_drag_object(request):
    object_type = request.POST.get('object_type')
    section = get_object_or_404(TrackSection, pk=request.POST.get('section_id'))
    if object_type == 'train':
        target = get_object_or_404(Train, pk=request.POST.get('object_id'))
        label = f'Состав {target.train_number}'
        comment = 'Перемещение состава мышкой на схеме путей'
    else:
        return JsonResponse({'ok': False, 'message': 'На схеме допускается перемещение только составов'}, status=400)
    if target.current_section_id == section.id:
        return JsonResponse({'ok': True, 'message': f'{label} уже находится на этом участке'})
    try:
        move_object(user=request.user, target=target, section=section, comment=comment)
    except ValueError as exc:
        return JsonResponse({'ok': False, 'message': str(exc)}, status=400)
    return JsonResponse({'ok': True, 'message': f'{label} перемещен на участок {section}'})


@role_required(Role.ADMIN, Role.OPERATOR)
def documents(request):
    return render(request, 'rail/documents.html', {'documents': Document.objects.select_related('train')})


@role_required(Role.ADMIN, Role.OPERATOR)
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


@role_required(Role.ADMIN, Role.OPERATOR)
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


@role_required(Role.ADMIN, Role.OPERATOR)
def reports(request):
    trains = Train.objects.all()
    wagons = Wagon.objects.all()
    movements = MovementHistory.objects.select_related('train', 'wagon', 'to_track', 'to_section')

    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    status = request.GET.get('status')
    track = request.GET.get('track')

    if date_from:
        trains = trains.filter(arrival_datetime__date__gte=date_from)
        wagons = wagons.filter(arrival_datetime__date__gte=date_from)
        movements = movements.filter(moved_at__date__gte=date_from)
    if date_to:
        trains = trains.filter(arrival_datetime__date__lte=date_to)
        wagons = wagons.filter(arrival_datetime__date__lte=date_to)
        movements = movements.filter(moved_at__date__lte=date_to)
    if status:
        wagons = wagons.filter(status=status)
    if track:
        trains = trains.filter(current_track_id=track)
        wagons = wagons.filter(current_track_id=track)
        movements = movements.filter(to_track_id=track)

    movements = movements[:50]
    status_labels = dict(Wagon.STATUS_CHOICES)
    wagon_statuses = [
        {'status': status_labels.get(row['status'], row['status']), 'total': row['total']}
        for row in wagons.values('status').annotate(total=Count('id'))
    ]

    placement_report = trains.exclude(current_section__isnull=True)
    daily_report = trains.filter(arrival_datetime__date=timezone.localdate())
    documents_report = Document.objects.filter(train__in=trains).exclude(ocr_status='confirmed')

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
    return render(request, 'rail/reports.html', {
        'trains': trains[:20], 'wagons': wagons[:20], 'movements': movements, 'wagon_statuses': wagon_statuses,
        'placement_report': placement_report[:20], 'daily_report': daily_report[:20], 'documents_report': documents_report[:20],
        'tracks': RailwayTrack.objects.all(), 'status_choices': Wagon.STATUS_CHOICES,
        'filters': {'date_from': date_from or '', 'date_to': date_to or '', 'status': status or '', 'track': track or ''},
    })


@login_required
def notifications(request):
    if request.method == 'POST':
        request.user.notifications.update(is_read=True)
        return redirect('notifications')
    return render(request, 'rail/notifications.html', {'notifications': request.user.notifications.all()})


@role_required(Role.ADMIN)
def admin_panel(request):
    logs = list(OperationLog.objects.select_related('user')[:100])
    train_ids = [log.object_id for log in logs if log.object_type == 'Train' and log.object_id]
    wagon_ids = [log.object_id for log in logs if log.object_type == 'Wagon' and log.object_id]
    train_map = {t.id: t.train_number for t in Train.objects.filter(id__in=train_ids)}
    wagon_map = {w.id: w.wagon_number for w in Wagon.objects.filter(id__in=wagon_ids)}
    for log in logs:
        if log.object_type == 'Train' and log.object_id in train_map:
            log.object_label = f"Состав {train_map[log.object_id]}"
        elif log.object_type == 'Wagon' and log.object_id in wagon_map:
            log.object_label = f"Вагон {wagon_map[log.object_id]}"
        elif log.object_type and log.object_id:
            log.object_label = f"{log.object_type} #{log.object_id}"
        else:
            log.object_label = '—'
    return render(request, 'rail/admin_panel.html', {'logs': logs, 'users_count': User.objects.count()})
