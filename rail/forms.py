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
    'file': 'Файл документа',
    'document_type': 'Тип документа',
    'wagon_count': 'Количество вагонов',
    'arrival_date': 'Дата прибытия',
    'raw_text': 'Распознанный текст',
    'confidence': 'Уверенность OCR, %',
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
        fields = ['train_number', 'arrival_datetime', 'departure_datetime', 'status', 'cargo_type', 'current_track', 'current_section', 'comment']
        widgets = {'arrival_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local'}), 'departure_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_design_classes()


class WagonForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Wagon
        fields = ['wagon_number', 'train', 'cargo_type', 'cargo_description', 'status', 'current_track', 'current_section', 'arrival_datetime', 'departure_datetime', 'comment']
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
    target_type = forms.ChoiceField(choices=[('train', 'Состав'), ('wagon', 'Вагон')])
    train = forms.ModelChoiceField(queryset=Train.objects.all(), required=False)
    wagon = forms.ModelChoiceField(queryset=Wagon.objects.all(), required=False)
    section = forms.ModelChoiceField(queryset=TrackSection.objects.none())
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['section'].queryset = TrackSection.objects.select_related('track').all()
        self.apply_design_classes()
