"""Tests del módulo Demo SIN BD ni red: prueban las piezas estilo milpa de forma EJECUTABLE
(serializers Pydantic, Pipeline de limpieza, Mailables + i18n, render de templates de correo,
registro de @job/@cron_task y del handler del Mediator). "Código sin demostración ejecutable son
promesas": esto las cumple. No dispara observers ni SMTP (eso es prueba manual con Mailpit)."""

from __future__ import annotations

import importlib

from milpa.Core.Mediator import registered_handlers, reset_handlers
from milpa.Core.Pipeline import Pipeline
from milpa.Core.Translate import t
from milpa.Core.View.TemplateEngine import template_engine
from milpa.Modules.Demo.Commands import ArchiveNote
from milpa.Modules.Demo.Jobs.ExportNotesJob import export_user_notes
from milpa.Modules.Demo.Mail.NewUserAdminMailable import NewUserAdminMailable
from milpa.Modules.Demo.Mail.NoteCreatedMailable import NoteCreatedMailable
from milpa.Modules.Demo.Mail.ShareNoteMailable import ShareNoteMailable
from milpa.Modules.Demo.Pipes.CleanContent import CollapseWhitespace, NoteDraft, TrimContent
from milpa.Modules.Demo.Serializers import NoteOut, UserOut


# --------------------------------------------------------- serializers (computed_field)
def test_note_serializer_truncates_excerpt() -> None:
    short = NoteOut(id=1, title="t", body="corto", owner_id=1).model_dump()
    assert short["excerpt"] == "corto"
    long = NoteOut(id=1, title="t", body="x" * 200, owner_id=1).model_dump()
    assert long["excerpt"].endswith("…") and len(long["excerpt"]) <= 81


def test_user_serializer_is_admin_is_computed() -> None:
    assert UserOut(id=1, name="A", email="a@x.com", roles=["admin"]).model_dump()["is_admin"] is True
    assert UserOut(id=2, name="B", email="b@x.com", roles=["editor"]).model_dump()["is_admin"] is False


# --------------------------------------------------------- pipeline (limpieza de contenido)
def test_clean_content_pipeline_trims_and_collapses() -> None:
    draft: NoteDraft = (
        Pipeline()
        .send(NoteDraft(title="  Hola    mundo  ", body="  cuerpo  "))
        .through([TrimContent(), CollapseWhitespace()])
        .then_return()
    )
    assert draft.title == "Hola mundo"
    assert draft.body == "cuerpo"


# --------------------------------------------------------- mailables + i18n
def test_note_created_mailable_subject_is_translated() -> None:
    assert NoteCreatedMailable("Mi nota", "es").build().subject == "Tu nota «Mi nota» fue creada"
    assert NoteCreatedMailable("My note", "en").build().subject == "Your note “My note” was created"


def test_i18n_catalog_resolves_both_locales() -> None:
    assert t("demo/NoteCreated.greeting", {}, "es") == "¡Hola!"
    assert t("demo/NoteCreated.greeting", {}, "en") == "Hi!"


def test_new_user_admin_mailable_build() -> None:
    content = NewUserAdminMailable("Ana", "ana@x.com").build()
    assert "Ana" in content.subject
    assert content.template == "demo/emails/new_user_admin.html.j2"
    assert content.context["sender_name"] == "Equipo milpa"  # firma común de DemoMailable


def test_email_templates_render_extending_signed_layout() -> None:
    # Render real de los 3 templates (extienden Emails/Trans/mastersigned): si el extends, el
    # bloque content o un t() estuvieran rotos, esto explota. No manda nada (solo renderiza).
    cases = [
        NoteCreatedMailable("Mi nota", "es").build(),
        NewUserAdminMailable("Ana", "ana@x.com").build(),
        ShareNoteMailable("Título", "cuerpo", "Beto").build(),
    ]
    for content in cases:
        html = template_engine.render(content.template, {"locale": "es", **content.context})
        assert "<html" in html.lower()  # el layout firmado renderizó
        assert "cid:logo" in html  # el logo de marca (StackCraft) se embebió por CID


# --------------------------------------------------------- job / cron (registro)
def test_export_notes_is_a_dispatchable_job() -> None:
    assert export_user_notes.name == "demo.export_notes"
    assert hasattr(export_user_notes, "dispatch")  # es un Job (no una task pelada)


def test_daily_digest_is_a_cron_task() -> None:
    from milpa.Modules.Demo.Crons.DailyDigestCron import daily_digest

    assert daily_digest.name == "demo.daily_digest"


# --------------------------------------------------------- mediator (registro del handler)
def test_archive_note_handler_is_registered() -> None:
    # El registro de handlers es un global compartido que otros tests resetean; reseteamos +
    # recargamos el módulo para re-ejecutar `@handles(ArchiveNote)` y probar el wiring sin
    # depender del orden de ejecución de la suite.
    reset_handlers()
    handler_mod = importlib.import_module("milpa.Modules.Demo.Handlers.ArchiveNoteHandler")
    importlib.reload(handler_mod)
    assert registered_handlers().get(ArchiveNote) is handler_mod.ArchiveNoteHandler


# --------------------------------------------------------- policies (ABAC) descubribles
def test_note_policies_are_discoverable_and_grant_moderator() -> None:
    # Regresión: el handler ArchiveNote hace Gate.authorize("note.update"); si las @policy del Demo
    # no se descubren (p. ej. olvidar import_all_policies en la CLI), el Gate DENIEGA. Probamos que
    # se registran y conceden a un moderador (editor/admin). reset+reload para no depender del orden.
    from milpa.Core.Auth import Gate
    from milpa.Core.Auth.Authorization import reset_policies

    reset_policies()
    policies_mod = importlib.import_module("milpa.Modules.Demo.Policies")
    importlib.reload(policies_mod)  # re-ejecuta @policy("note.update") / @policy("note.delete")

    class _Note:
        owner_id = 999

    class _Moderator:
        def get_roles(self) -> list[str]:
            return ["editor"]

        def get_auth_identifier(self) -> int:
            return 1

    assert Gate.allows("note.update", _Note(), user=_Moderator()) is True
    assert Gate.allows("note.delete", _Note(), user=_Moderator()) is True
