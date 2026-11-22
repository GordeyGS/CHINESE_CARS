from django.core.management.base import BaseCommand, CommandError

from apps.cars.services.wikidata import WikidataClient, WikidataError, WikidataImporter


class Command(BaseCommand):
    help = (
        "Импортирует модели китайских марок из Wikidata (SPARQL API), фото с Wikimedia Commons и описания из Википедии. "
        "Новые модели создаются черновиками (is_active=False), заполненные поля существующих не меняются."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Показать результат без сохранения в БД.")
        parser.add_argument("--publish", action="store_true", help="Сразу сделать новые модели активными.")
        parser.add_argument("--no-images", action="store_true", help="Не запрашивать фото с Wikimedia Commons.")
        parser.add_argument("--no-descriptions", action="store_true", help="Не запрашивать описания из Википедии.")
        parser.add_argument("--timeout", type=float, default=60.0, help="Тайм-аут HTTP-запроса, с.")

    def handle(self, *args, **options):
        importer = WikidataImporter(WikidataClient(timeout=options["timeout"]))
        try:
            report = importer.run(
                publish=options["publish"],
                with_images=not options["no_images"],
                with_descriptions=not options["no_descriptions"],
                dry_run=options["dry_run"],
            )
        except WikidataError as error:
            raise CommandError(f"Импорт из Wikidata не выполнен: {error} База данных не изменена.") from error

        if options["verbosity"] >= 2:
            for title in report.created:
                self.stdout.write(f"  + {title}")
            for title, reason in report.skipped:
                self.stdout.write(f"  - {title}: {reason}")

        status = "активные" if options["publish"] else "черновики, is_active=False"
        prefix = "[dry-run] " if options["dry_run"] else ""
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}Создано моделей: {len(report.created)} ({status}); "
            f"дополнено существующих: {len(report.updated)}; без изменений: {len(report.unchanged)}; "
            f"пропущено: {len(report.skipped)}; фото с указанием автора: {report.images_found}; "
            f"описаний из Википедии: {report.descriptions_found}."
        ))
