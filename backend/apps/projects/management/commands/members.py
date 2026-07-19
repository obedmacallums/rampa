"""Out-of-band membership administration (002 R5).

Operator tool with full reach — it bypasses ownership checks, and is the only
path that can rescue a project whose sole owner was deleted (spec edge case).
"""

import uuid

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.projects.models import Project, ProjectMembership


class Command(BaseCommand):
    help = "List or modify project memberships (operator channel, bypasses ownership)"

    def add_arguments(self, parser):
        parser.add_argument("action", choices=["list", "add", "remove"])
        parser.add_argument("project", help="project name or id")
        parser.add_argument("username", nargs="?")
        parser.add_argument("--role", choices=ProjectMembership.Role.values, default="member")

    def handle(self, *args, **options):
        project = self._project(options["project"])
        action = options["action"]

        if action == "list":
            for m in project.memberships.select_related("user", "granted_by").order_by(
                "granted_at"
            ):
                granted_by = m.granted_by.username if m.granted_by else "system"
                self.stdout.write(f"{m.user.username}\t{m.role}\t{granted_by}\t{m.granted_at:%F}")
            return

        if not options["username"]:
            raise CommandError(f"'{action}' requires a username")
        try:
            user = get_user_model().objects.get(username=options["username"])
        except get_user_model().DoesNotExist:
            raise CommandError(f"user not found: {options['username']}") from None

        if action == "add":
            membership, created = ProjectMembership.objects.update_or_create(
                project=project, user=user, defaults={"role": options["role"]}
            )
            self.stdout.write(
                f"membership {'created' if created else 'updated'}: "
                f"{user.username} {membership.role} on {project.name}"
            )
        else:
            deleted, _ = ProjectMembership.objects.filter(project=project, user=user).delete()
            if not deleted:
                raise CommandError(f"{user.username} is not a member of {project.name}")
            self.stdout.write(f"membership removed: {user.username} from {project.name}")

    def _project(self, ref: str) -> Project:
        try:
            uuid.UUID(ref)
            lookup = {"id": ref}
        except ValueError:
            lookup = {"name__iexact": ref}
        try:
            return Project.objects.get(**lookup)
        except Project.DoesNotExist:
            raise CommandError(f"project not found: {ref}") from None
