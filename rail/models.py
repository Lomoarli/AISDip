from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class Role(models.Model):
    ADMIN = 'admin'
    OPERATOR = 'operator'
    DISPATCHER = 'dispatcher'
    ROLE_CHOICES = [(ADMIN, 'Администратор'), (OPERATOR, 'Оператор'), (DISPATCHER, 'Маневровый диспетчер')]
    name = models.CharField('Роль', max_length=32, choices=ROLE_CHOICES, unique=True)

    def __str__(self):
        return self.get_name_display()


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.username}: {self.role or "без роли"}'


class RailwayTrack(models.Model):
    name = models.CharField('Название', max_length=120)
    number = models.CharField('Номер', max_length=20, unique=True)
    type = models.CharField('Тип', max_length=80, default='приемо-отправочный')
    length = models.PositiveIntegerField('Длина, м', default=850)
    capacity = models.PositiveIntegerField('Вместимость вагонов', default=55)
    description = models.TextField('Описание', blank=True)
    is_active = models.BooleanField('Активен', default=True)

    class Meta:
        ordering = ['number']

    def __str__(self):
        return f'Путь {self.number} — {self.name}'


class TrackSection(models.Model):
    track = models.ForeignKey(RailwayTrack, on_delete=models.CASCADE, related_name='sections')
    name = models.CharField('Участок', max_length=120)
    position_start = models.PositiveIntegerField('Начало, м', default=0)
    position_end = models.PositiveIntegerField('Конец, м', default=100)
    max_wagons = models.PositiveIntegerField('Максимум вагонов', default=10)
    coordinates_x = models.PositiveIntegerField(default=0)
    coordinates_y = models.PositiveIntegerField(default=0)
    is_occupied = models.BooleanField('Занят', default=False)

    class Meta:
        ordering = ['track__number', 'position_start']

    def __str__(self):
        return f'{self.track.number}: {self.name}'


class Train(models.Model):
    ARRIVED = 'arrived'
    PLACED = 'placed'
    PROCESSING = 'processing'
    READY = 'ready_to_depart'
    DEPARTED = 'departed'
    STATUS_CHOICES = [(ARRIVED, 'Прибыл'), (PLACED, 'Размещен'), (PROCESSING, 'В обработке'), (READY, 'Готов к отправлению'), (DEPARTED, 'Отправлен')]
    train_number = models.CharField('Номер состава', max_length=40, unique=True)
    arrival_datetime = models.DateTimeField('Дата прибытия', default=timezone.now)
    departure_datetime = models.DateTimeField('Дата отправления', null=True, blank=True)
    status = models.CharField('Статус', max_length=32, choices=STATUS_CHOICES, default=ARRIVED)
    cargo_type = models.CharField('Тип груза', max_length=120, blank=True)
    current_track = models.ForeignKey(RailwayTrack, on_delete=models.SET_NULL, null=True, blank=True)
    current_section = models.ForeignKey(TrackSection, on_delete=models.SET_NULL, null=True, blank=True)
    comment = models.TextField('Комментарий', blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-arrival_datetime']

    def __str__(self):
        return self.train_number


class Wagon(models.Model):
    STATUS_CHOICES = [('loaded', 'Груженый'), ('unloaded', 'Порожний'), ('waiting_unload', 'Ожидает выгрузки'), ('unloading', 'Выгружается'), ('maintenance', 'Ремонт'), ('ready_to_depart', 'Готов к отправлению'), ('departed', 'Отправлен')]
    wagon_number = models.CharField('Номер вагона', max_length=40, unique=True)
    train = models.ForeignKey(Train, on_delete=models.CASCADE, related_name='wagons')
    cargo_type = models.CharField('Тип груза', max_length=120, blank=True)
    cargo_description = models.TextField('Описание груза', blank=True)
    status = models.CharField('Статус', max_length=32, choices=STATUS_CHOICES, default='waiting_unload')
    current_track = models.ForeignKey(RailwayTrack, on_delete=models.SET_NULL, null=True, blank=True)
    current_section = models.ForeignKey(TrackSection, on_delete=models.SET_NULL, null=True, blank=True)
    arrival_datetime = models.DateTimeField('Дата прибытия', default=timezone.now)
    departure_datetime = models.DateTimeField('Дата отправления', null=True, blank=True)
    comment = models.TextField('Комментарий', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['wagon_number']

    def __str__(self):
        return self.wagon_number


class MovementHistory(models.Model):
    OBJECT_CHOICES = [('train', 'Состав'), ('wagon', 'Вагон')]
    object_type = models.CharField(max_length=16, choices=OBJECT_CHOICES)
    train = models.ForeignKey(Train, on_delete=models.CASCADE, null=True, blank=True)
    wagon = models.ForeignKey(Wagon, on_delete=models.CASCADE, null=True, blank=True)
    from_track = models.ForeignKey(RailwayTrack, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    from_section = models.ForeignKey(TrackSection, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    to_track = models.ForeignKey(RailwayTrack, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    to_section = models.ForeignKey(TrackSection, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    moved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    moved_at = models.DateTimeField(auto_now_add=True)
    comment = models.TextField(blank=True)

    class Meta:
        ordering = ['-moved_at']


class Document(models.Model):
    OCR_CHOICES = [('uploaded', 'Загружен'), ('processing', 'Обрабатывается'), ('recognized', 'Распознан'), ('error', 'Ошибка'), ('confirmed', 'Подтвержден')]
    train = models.ForeignKey(Train, on_delete=models.CASCADE, related_name='documents')
    file = models.FileField(upload_to='documents/')
    document_type = models.CharField('Тип документа', max_length=80, default='накладная')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    ocr_status = models.CharField(max_length=24, choices=OCR_CHOICES, default='uploaded')
    recognized_text = models.TextField(blank=True)

    class Meta:
        ordering = ['-uploaded_at']


class OCRResult(models.Model):
    document = models.OneToOneField(Document, on_delete=models.CASCADE, related_name='ocr_result')
    train_number = models.CharField(max_length=40, blank=True)
    wagon_count = models.PositiveIntegerField(null=True, blank=True)
    cargo_type = models.CharField(max_length=120, blank=True)
    arrival_date = models.DateField(null=True, blank=True)
    raw_text = models.TextField(blank=True)
    confidence = models.PositiveIntegerField(default=70)
    confirmed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)


class OperationLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=80)
    object_type = models.CharField(max_length=80, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class Notification(models.Model):
    TYPE_CHOICES = [('info', 'Информация'), ('warning', 'Предупреждение'), ('error', 'Ошибка'), ('success', 'Успех')]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=160)
    message = models.TextField()
    type = models.CharField(max_length=16, choices=TYPE_CHOICES, default='info')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
