from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('rail', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='train',
            name='wagon_count',
            field=models.PositiveIntegerField(default=0, verbose_name='Количество вагонов (по документу/плану)'),
        ),
        migrations.AddField(
            model_name='wagon',
            name='cargo_quantity',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=12, null=True, verbose_name='Количество груза'),
        ),
        migrations.AddField(
            model_name='wagon',
            name='cargo_unit',
            field=models.CharField(blank=True, default='т', max_length=16, verbose_name='Единица измерения'),
        ),
        migrations.AlterField(
            model_name='wagon',
            name='status',
            field=models.CharField(choices=[('arrived', 'Прибыл'), ('waiting_unload', 'Ожидает разгрузки'), ('unloading', 'На разгрузке'), ('unloaded', 'Разгружен'), ('loaded', 'Загружен'), ('maintenance', 'На обслуживании'), ('ready_to_depart', 'Готов к отправке'), ('departed', 'Отправлен')], default='waiting_unload', max_length=32, verbose_name='Статус'),
        ),
    ]
