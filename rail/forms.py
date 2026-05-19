from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import Document, OCRResult, TrackSection, Train, Wagon


CONTROL_LABELS = {
    'train_number': 'Номер состава',
    'arrival_datetime': 'Дата и время прибытия',
    'departure_datetime': 'Дата и время отправления',
    'status': 'Статус',
    'cargo_type': 'Тип груза',
    'current_track': 'Текущий путь',
    'current_section': 'Текущий участок',
    'comment': 'Комментарий',
    'wagon_number': 'Номер вагона',
    'train': 'Состав',
    'cargo_description': 'Описание груза',
    'cargo_quantity': 'Количество груза',
    'cargo_unit': 'Единица измерения',
    'wagon_count': 'Количество вагонов',
    'file': 'Файл документа',
    'document_type': 'Тип документа',
    'wagon_count': 'Количество вагонов',
    'arrival_date': 'Дата прибытия',
    'raw_text': 'Распознанный текст',
    'confidence': 'Уверенность OCR, %',
    'moving_object': 'Объект для перемещения',
    'target_type': 'Что перемещаем',
    'wagon': 'Вагон',
    'section': 'Новый участок',
}

PLACEHOLDERS = {
    'train_number': 'Например: 7701',
    'wagon_number': 'Например: 54000001',
    'cargo_type': 'Например: уголь, металл, лес',
    'cargo_description': 'Краткое описание груза',
    'comment': 'Дополнительная информация для журнала',
    'document_type': 'Например: накладная РЖД',
    'raw_text': 'Здесь появится текст после OCR',
}


class StyledFormMixin:
    """Adds rounded, Russian-labelled, Bootstrap-like widgets to Django forms."""

    def apply_design_classes(self):
        for name, field in self.fields.items():
            field.label = field.label or CONTROL_LABELS.get(name, name)
            if name in CONTROL_LABELS:
                field.label = CONTROL_LABELS[name]
            if isinstance(field, forms.ModelChoiceField):
                field.empty_label = 'Выберите значение'
            widget = field.widget
            if isinstance(widget, (forms.Select, forms.SelectMultiple)):
                css_class = 'form-select rounded-select'
            elif isinstance(widget, forms.CheckboxInput):
                css_class = 'form-check-input'
            elif isinstance(widget, forms.FileInput):
                css_class = 'form-control file-control'
            else:
                css_class = 'form-control'
            existing = widget.attrs.get('class', '')
            widget.attrs['class'] = f'{existing} {css_class}'.strip()
            if name in PLACEHOLDERS:
                widget.attrs.setdefault('placeholder', PLACEHOLDERS[name])
            field.error_messages.update({
                'required': 'Заполните это поле.',
                'invalid': 'Проверьте корректность значения.',
            })


class RussianLoginForm(StyledFormMixin, AuthenticationForm):
    username = forms.CharField(label='Логин', widget=forms.TextInput(attrs={'placeholder': 'Введите логин'}))
    password = forms.CharField(label='Пароль', widget=forms.PasswordInput(attrs={'placeholder': 'Введите пароль'}))
    error_messages = {
        'invalid_login': 'Введите правильные логин и пароль. Оба поля чувствительны к регистру.',
        'inactive': 'Этот пользователь отключен.',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_design_classes()


class TrainForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Train
        fields = ['train_number', 'arrival_datetime', 'departure_datetime', 'wagon_count', 'status', 'cargo_type', 'current_track', 'current_section', 'comment']
        widgets = {'arrival_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local'}), 'departure_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_design_classes()


class WagonForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Wagon
        fields = ['wagon_number', 'train', 'cargo_type', 'cargo_quantity', 'cargo_unit', 'cargo_description', 'status', 'current_track', 'current_section', 'arrival_datetime', 'departure_datetime', 'comment']
        widgets = {'arrival_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local'}), 'departure_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_design_classes()


class DocumentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Document
        fields = ['train', 'file', 'document_type']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_design_classes()


class OCRConfirmForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = OCRResult
        fields = ['train_number', 'wagon_count', 'cargo_type', 'arrival_date', 'raw_text', 'confidence']
        widgets = {'arrival_date': forms.DateInput(attrs={'type': 'date'}), 'raw_text': forms.Textarea(attrs={'rows': 10})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_design_classes()


class MoveForm(StyledFormMixin, forms.Form):
    moving_object = forms.ChoiceField(choices=[])
    section = forms.ModelChoiceField(queryset=TrackSection.objects.none())
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        trains = Train.objects.exclude(status=Train.DEPARTED).order_by('train_number')
        wagons = Wagon.objects.exclude(status='departed').select_related('train').order_by('wagon_number')
        self.fields['moving_object'].choices = [('', 'Выберите состав или вагон')] + [
            (f'train:{train.id}', f'🚆 Состав {train.train_number}') for train in trains
        ] + [
            (f'wagon:{wagon.id}', f'▣ Вагон {wagon.wagon_number} — состав {wagon.train.train_number}') for wagon in wagons
        ]
        self.fields['section'].queryset = TrackSection.objects.select_related('track').all()
        self.apply_design_classes()

    def clean_moving_object(self):
        value = self.cleaned_data['moving_object']
        try:
            object_type, object_id = value.split(':', 1)
        except ValueError as exc:
            raise forms.ValidationError('Выберите состав или вагон из списка.') from exc
        if object_type not in {'train', 'wagon'} or not object_id.isdigit():
            raise forms.ValidationError('Выберите корректный объект для перемещения.')
        return value

    def get_target(self):
        object_type, object_id = self.cleaned_data['moving_object'].split(':', 1)
        model = Train if object_type == 'train' else Wagon
        return model.objects.get(pk=object_id)
