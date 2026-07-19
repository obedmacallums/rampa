"""Operator-provisioned accounts (FR-015): no self-registration exists."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create (or update the password of) a platform user"

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("--password", required=True)

    def handle(self, *args, **options):
        if not options["password"]:
            raise CommandError("--password must not be empty")
        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(username=options["username"])
        user.set_password(options["password"])
        user.save()
        self.stdout.write(f"user {'created' if created else 'updated'}: {user.username}")
