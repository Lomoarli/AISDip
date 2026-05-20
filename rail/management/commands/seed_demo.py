from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from rail.models import RailwayTrack, Role, TrackSection, Train, UserProfile, Wagon
from rail.services import log_action, refresh_section_occupancy


class Command(BaseCommand):
    help = 'Создает демонстрационные роли, пользователей, пути, составы и вагоны.'

    def handle(self, *args, **options):
        roles = {code: Role.objects.get_or_create(name=code)[0] for code in ('admin', 'operator', 'dispatcher')}
        users = [('admin', 'admin123', roles['admin'], True), ('operator', 'operator123', roles['operator'], False), ('dispatcher', 'dispatcher123', roles['dispatcher'], False)]
        for username, password, role, is_staff in users:
            user, created = User.objects.get_or_create(username=username, defaults={'is_staff': is_staff, 'is_superuser': username == 'admin'})
            if created:
                user.set_password(password)
                user.save()
            UserProfile.objects.update_or_create(user=user, defaults={'role': role})
        for i in range(1, 5):
            track, _ = RailwayTrack.objects.get_or_create(number=str(i), defaults={'name': f'Путь №{i}', 'length': 900, 'capacity': 60, 'type': 'внутризаводской'})
            for j in range(1, 4):
                TrackSection.objects.get_or_create(track=track, name=f'Участок {j}', defaults={'position_start': (j - 1) * 300, 'position_end': j * 300, 'max_wagons': 20, 'coordinates_x': j * 120, 'coordinates_y': i * 90})
        admin = User.objects.get(username='admin')
        first_section = TrackSection.objects.select_related('track').first()
        train, _ = Train.objects.get_or_create(train_number='7701', defaults={'cargo_type': 'уголь', 'current_track': first_section.track, 'current_section': first_section, 'status': Train.PLACED, 'created_by': admin, 'arrival_datetime': timezone.now()})
        for n in range(1, 7):
            Wagon.objects.get_or_create(wagon_number=f'54{n:06d}', defaults={'train': train, 'cargo_type': 'уголь', 'cargo_description': 'Демонстрационный вагон', 'status': 'waiting_unload', 'current_track': first_section.track, 'current_section': first_section})
        Train.objects.get_or_create(train_number='8802', defaults={'cargo_type': 'металл', 'status': Train.ARRIVED, 'created_by': admin})
        refresh_section_occupancy()
        log_action(admin, 'Наполнение демо-данными', description='Созданы роли, пользователи, пути, составы и вагоны')
        self.stdout.write(self.style.SUCCESS('Демо-данные созданы. Логины: admin/admin123, operator/operator123, dispatcher/dispatcher123'))
