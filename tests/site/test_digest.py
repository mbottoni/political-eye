"""The weekly email: which changes are the week's, what it says, and that it sends only with the three secrets."""

import os
import subprocess
from datetime import date

import pandas as pd

from politicaleye.io import write_csv
from politicaleye.site import digest as dg
from politicaleye.site import mudancas as m

from .test_mudancas import MEI_NAME, PERSON_NAME, world


def test_week_is_monday_to_monday():
    assert dg.week(date(2026, 11, 16)) == (date(2026, 11, 9), date(2026, 11, 16))   # a Monday
    assert dg.week(date(2026, 11, 18)) == (date(2026, 11, 9), date(2026, 11, 16))   # a run two days late covers the same week
    assert dg.span(date(2026, 11, 9), date(2026, 11, 16), "pt") == "9 a 15 de novembro de 2026"
    assert dg.span(date(2026, 10, 26), date(2026, 11, 2), "en") == "26 October to 1 November 2026"


def test_without_history_the_week_is_the_rows_dated_in_it(tmp_path):
    d = world(tmp_path)
    m.build(d)
    c = dg.collect(d, date(2026, 11, 16))
    assert c["how"] == "dates"
    assert set(c["fontes"]["sancoes"]["rows"].data) == {"2026-11-12", "2026-11-13"}
    assert c["fontes"]["pncp"]["rows"].empty   # contracts of Nov 5, the week before
    h = dg.headline(c)
    assert h["entraram"] == 2 and h["sairam"] == 1 and h["pessoas_entraram"] == 1
    subject, html, text = dg.build(c, "pt")
    assert subject.startswith("political-eye · 9 a 15 de novembro de 2026: 2 empresas entraram e 1 saíram")
    assert "BARRED LTDA" in html and "Empresa individual (nome omitido)" in html and "Pessoas punidas são contadas" in text
    for s in (subject, html, text):   # no person, no individual firm's name
        assert PERSON_NAME not in s and "JOAO SILVA" not in s and MEI_NAME not in s
    _, both, both_text = dg.build(c, "both")
    assert "O que mudou de" in both and "What changed, 9 to 15 November 2026" in both and "Individual firm (name withheld)" in both_text


def git(repo, *args, when=None):
    env = os.environ | ({"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when} if when else {})
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args], check=True, capture_output=True, env=env)


def test_with_history_the_week_is_what_was_committed_in_it(tmp_path):
    d = world(tmp_path)
    m.build(d)
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "before the week", when="2026-11-08T12:00:00Z")
    # During the week: a CEPIM snapshot published late adds an entry dated before the week.
    ch = pd.read_csv(d / "sancoes" / "changes.csv", dtype=str, keep_default_na=False)
    late = {"data": "2026-11-04", "lista": "cepim", "codigo": "77", "mudanca": "entrou", "tipo_de_pessoa": "J", "documento": "66666666000166", "nome": "ASSOCIACAO TARDIA"}
    write_csv(pd.concat([ch, pd.DataFrame([late])], ignore_index=True), d / "sancoes" / "changes.csv")
    m.build(d)
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "during the week", when="2026-11-12T12:00:00Z")
    # After the week ended: not in this email, in the next one.
    write_csv(pd.concat([ch, pd.DataFrame([late, late | {"codigo": "78", "documento": "77777777000177", "nome": "DEPOIS LTDA"}])], ignore_index=True),
              d / "sancoes" / "changes.csv")
    m.build(d)
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "after the week", when="2026-11-16T06:00:00Z")

    c = dg.collect(d, date(2026, 11, 16))
    assert c["how"] == "git"
    s = c["fontes"]["sancoes"]["rows"]
    assert s.chave.tolist() == ["cepim:entrou:66666666000166"]   # recorded this week, though dated Nov 4
    assert c["fontes"]["camara"]["rows"].empty                    # nothing new there
    _, html, _ = dg.build(c, "pt")
    assert "ASSOCIACAO TARDIA" in html and "DEPOIS LTDA" not in html and "BARRED LTDA" not in html


class FakeSMTP:
    sent = []

    def __init__(self, host, port, timeout=None):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self, context=None):
        pass

    def login(self, user, password):
        self.user = user

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


def test_sends_only_with_the_three_secrets(tmp_path, monkeypatch):
    monkeypatch.setattr(dg.smtplib, "SMTP", FakeSMTP)
    for k in ("SMTP_USER", "SMTP_PASSWORD", "EMAIL_TO"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("SMTP_USER", "bot@example.com")
    assert dg.send("s", "<p>h</p>", "t", tmp_path / "out") is False   # one secret missing: a dry run
    assert (tmp_path / "out" / "email.html").read_text() == "<p>h</p>" and not FakeSMTP.sent
    monkeypatch.setenv("SMTP_PASSWORD", "app-password")
    monkeypatch.setenv("EMAIL_TO", "me@example.com")
    assert dg.send("Assunto", "<p>h</p>", "texto", tmp_path / "out") is True
    msg = FakeSMTP.sent[-1]
    assert msg["To"] == "me@example.com" and msg["Subject"] == "Assunto"
    assert [p.get_content_type() for p in msg.iter_parts()] == ["text/plain", "text/html"]
