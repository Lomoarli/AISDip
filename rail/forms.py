from django import forms
from .models import Document, OCRResult, TrackSection, Train, Wagon


class TrainForm(forms.ModelForm):
    class Meta:
        model = Train
        fields = ['train_number', 'arrival_datetime', 'departure_datetime', 'status', 'cargo_type', 'current_track', 'current_section', 'comment']
        widgets = {'arrival_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local'}), 'departure_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local'})}


class WagonForm(forms.ModelForm):
    class Meta:
        model = Wagon
        fields = ['wagon_number', 'train', 'cargo_type', 'cargo_description', 'status', 'current_track', 'current_section', 'arrival_datetime', 'departure_datetime', 'comment']
        widgets = {'arrival_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local'}), 'departure_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local'})}


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['train', 'file', 'document_type']


class OCRConfirmForm(forms.ModelForm):
    class Meta:
        model = OCRResult
        fields = ['train_number', 'wagon_count', 'cargo_type', 'arrival_date', 'raw_text', 'confidence']
        widgets = {'arrival_date': forms.DateInput(attrs={'type': 'date'}), 'raw_text': forms.Textarea(attrs={'rows': 10})}


class MoveForm(forms.Form):
    target_type = forms.ChoiceField(choices=[('train', 'Состав'), ('wagon', 'Вагон')])
    train = forms.ModelChoiceField(queryset=Train.objects.all(), required=False)
    wagon = forms.ModelChoiceField(queryset=Wagon.objects.all(), required=False)
    section = forms.ModelChoiceField(queryset=TrackSection.objects.none())
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['section'].queryset = TrackSection.objects.select_related('track').all()
