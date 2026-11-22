from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand, CommandError

from apps.users.roles import CONTENT_APPS, setup_roles


class Command(BaseCommand):
    help = "Создаёт или обновляет группы Editor и Administrator с правами Django."

    def handle(self, *args, **options):
        if not Permission.objects.filter(content_type__app_label__in=CONTENT_APPS).exists():
            raise CommandError("Права моделей ещё не созданы. Сначала выполните: python manage.py migrate")
        for name, count in setup_roles().items():
            self.stdout.write(self.style.SUCCESS(f"{name}: {count} прав"))
