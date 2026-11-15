"""The weekly email: what the change logs (``data/site/mudancas/``, see mudancas.py) recorded in a week.

**Which changes are the week's.** The rows in the logs as committed by Monday 00:00 UTC that were not in them as
committed a week before, read from git. A change dated earlier but recorded this week (a CEPIM snapshot published
late, a day of contracts read on a later run) is not lost, nothing is sent twice, and a re-run renders the same email.
Without the repository's history (a copy of ``data/`` alone), or for a log that did not exist a week before, it falls
back to the rows dated in the week.

**Sending** follows b3-radar's weekly email: SMTP (Gmail with an App Password by default), credentials and recipients
only from the environment (``SMTP_USER``, ``SMTP_PASSWORD``, ``EMAIL_TO``; repository secrets in CI), never from the
repo. Without them it is a dry run: the email is written to ``out/`` (``email.html``, ``email.txt``), which CI keeps as
an artifact. ``EMAIL_LANG`` picks the language: ``pt`` (default), ``en`` or ``both``.

Tables with inline styles, 640 px wide, no images and no scripts: email clients run none. People are never named (the
logs already withhold individual firms' names), and the email repeats that sanctioned people are counted and that a
red flag is not evidence. See methodology/mudancas.md#weekly-email.
"""

from __future__ import annotations

import io
import json
import os
import smtplib
import ssl
import subprocess
from datetime import date, timedelta
from email.message import EmailMessage
from html import escape
from pathlib import Path

import pandas as pd

from .mudancas import FONTES, NOTAS, SITE, SUMMARY, brl, describe, num

TOP = 10       # changes listed per source; the rest are on the page
KEY = ["fonte", "tipo", "chave", "data"]
INK, INK2, MUTED, LINE, PAGE_BG, SURFACE = "#0b0b0b", "#52514e", "#6b6a65", "#e1e0d9", "#f4f4f1", "#ffffff"
COLOR = {"sancoes": "#e34948", "alertas": "#c98500", "emendas": "#1baf7a", "pncp": "#eb6834", "camara": "#2a78d6", "senado": "#6250d6"}
FONT = "-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
_MONTHS = {"pt": ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"],
           "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]}


def week(today: date) -> tuple[date, date]:
    """The week an email sent on ``today`` covers: Monday 00:00 UTC of the week before to this week's Monday."""
    end = today - timedelta(days=today.weekday())
    return end - timedelta(days=7), end


def span(start: date, end: date, lang: str) -> str:
    """'9 a 15 de novembro de 2026' / '9 to 15 November 2026' (the last day is the Sunday before ``end``)."""
    last = end - timedelta(days=1)
    m1, m2 = _MONTHS[lang][start.month - 1], _MONTHS[lang][last.month - 1]
    if lang == "pt":
        head = f"{start.day}" if start.month == last.month else f"{start.day} de {m1}" + ("" if start.year == last.year else f" de {start.year}")
        return f"{head} a {last.day} de {m2} de {last.year}"
    head = f"{start.day}" if start.month == last.month else f"{start.day} {m1}" + ("" if start.year == last.year else f" {start.year}")
    return f"{head} to {last.day} {m2} {last.year}"


# ------------------------------------------------------------------ the week's changes

def _git(repo: Path, *args: str) -> str | None:
    try:
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def _rev(repo: Path, when: date) -> str | None:
    """The last commit made before 00:00 UTC of ``when``."""
    out = _git(repo, "rev-list", "-1", f"--before={when.isoformat()}T00:00:00Z", "HEAD")
    return out.strip() or None if out is not None else None


def _csv(text: str | None) -> pd.DataFrame | None:
    return None if text is None else pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)


def collect(data: Path, today: date) -> dict:
    """Each source's changes recorded in the week (see the module's docstring), with its metadata."""
    start, end = week(today)
    repo = data.parent
    rel = os.path.relpath(data, repo)
    r_end, r_start = _rev(repo, end), _rev(repo, start)
    res = {"start": start, "end": end, "fontes": {}, "how": "git" if r_end else "dates"}
    for f in FONTES:
        path = f"{rel}/site/mudancas/{f}"
        if r_end:
            now, meta = _csv(_git(repo, "show", f"{r_end}:{path}.csv")), _git(repo, "show", f"{r_end}:{path}.json")
            then = _csv(_git(repo, "show", f"{r_start}:{path}.csv")) if r_start else pd.DataFrame(columns=KEY)
        else:
            p = data / "site" / "mudancas" / f"{f}.csv"
            now = pd.read_csv(p, dtype=str, keep_default_na=False) if p.exists() else None
            meta = (data / "site" / "mudancas" / f"{f}.json").read_text() if (data / "site" / "mudancas" / f"{f}.json").exists() else None
            then = None
        if now is None or meta is None:
            continue
        if then is None:   # no history to compare with: the rows dated in the week
            rows = now[(now.data >= start.isoformat()) & (now.data < end.isoformat())]
        else:
            seen = set(map(tuple, then[KEY].values)) if len(then) else set()
            rows = now[pd.Series([k not in seen for k in map(tuple, now[KEY].values)], index=now.index, dtype=bool)]
            # An older-contracts count that grew on a day already logged: the growth is this week's.
            hist = now.tipo.str.endswith("_historico") & now.index.isin(now.index.difference(rows.index))
            if hist.any() and len(then):
                old = then.set_index(KEY)
                grown = []
                for r in now[hist].itertuples(index=False):
                    k = (r.fonte, r.tipo, r.chave, r.data)
                    if k in old.index:
                        dn = int(float(r.n or 0)) - int(float(old.loc[k].n or 0))
                        if dn > 0:
                            dv = float(r.valor or 0) - float(old.loc[k].valor or 0)
                            grown.append(r._asdict() | {"n": str(dn), "valor": f"{dv:.2f}"})
                if grown:
                    rows = pd.concat([rows, pd.DataFrame(grown)], ignore_index=True)
        rows = rows.assign(valor=pd.to_numeric(rows.valor, errors="coerce"), n=pd.to_numeric(rows.n, errors="coerce")).reset_index(drop=True)
        res["fontes"][f] = {"meta": json.loads(meta), "rows": rows}
    return res


# ------------------------------------------------------------------ what the email says

def headline(c: dict) -> dict:
    """The week in numbers, for the subject and the tiles."""
    get = lambda f: c["fontes"].get(f, {}).get("rows", pd.DataFrame(columns=[*KEY, "n", "valor"]))   # noqa: E731
    sa, al, em, pn = get("sancoes"), get("alertas"), get("emendas"), get("pncp")
    who = lambda t, end: t.chave[t.tipo.str.endswith(end)].str.split(":").str[-1].nunique() if len(t) else 0   # noqa: E731
    ppl = lambda t, part: int(pd.to_numeric(t.n[t.tipo.str.contains(part) & t.tipo.str.endswith("_pessoas")], errors="coerce").fillna(0).sum()) if len(t) else 0   # noqa: E731
    money = lambda t: float(pd.to_numeric(t.valor, errors="coerce").fillna(0).sum()) if len(t) else 0.0   # noqa: E731
    hist = al.tipo.str.endswith("_historico") if len(al) else pd.Series(dtype=bool)
    return {"entraram": who(sa, "_entrou"), "sairam": who(sa, "_saiu"), "pessoas_entraram": ppl(sa, "_entrou_"), "pessoas_sairam": ppl(sa, "_saiu_"),
            "sinais": int((~hist).sum()) if len(al) else 0, "antigos": int(pd.to_numeric(al.n[hist], errors="coerce").fillna(0).sum()) if len(al) else 0,
            "emendas": len(em), "emendas_valor": money(em), "contratos": len(pn), "contratos_valor": money(pn),
            "total": sum(len(x["rows"]) for x in c["fontes"].values())}


def subject(c: dict, lang: str) -> str:
    h, pt = headline(c), lang == "pt"
    when = span(c["start"], c["end"], lang)
    if not h["total"]:
        return f"political-eye · {when}: nada novo registrado" if pt else f"political-eye · {when}: nothing new recorded"
    bits = []
    if h["entraram"] or h["sairam"]:
        bits.append(f"{num(h['entraram'], lang)} empresas entraram e {num(h['sairam'], lang)} saíram das listas de sanções" if pt
                    else f"{num(h['entraram'], lang)} companies entered and {num(h['sairam'], lang)} left the sanctions lists")
    if h["sinais"]:
        bits.append(f"{num(h['sinais'], lang)} {'sinal de alerta novo' if h['sinais'] == 1 else 'sinais de alerta novos'}" if pt
                    else f"{num(h['sinais'], lang)} new red {'flag' if h['sinais'] == 1 else 'flags'}")
    return f"political-eye · {when}: " + "; ".join(bits[:2]) if bits else f"political-eye · {when}"


def _top(f: str, rows: pd.DataFrame) -> pd.DataFrame:
    """The changes an email lists for a source: the largest first, companies entering a list before those leaving,
    counts of people left to the summary line, counts of older contracts last."""
    t = rows.assign(_v=pd.to_numeric(rows.valor, errors="coerce").fillna(0))
    if f == "sancoes":
        t = t[~t.tipo.str.endswith("_pessoas")]
        t = t.assign(_in=~t.tipo.str.endswith("_entrou")).sort_values(["_in", "_v", "data", "chave"], ascending=[True, False, False, True])
    elif f in ("camara", "senado"):
        t = t.sort_values(["data", "chave"], ascending=[False, True])
    else:
        t = t.assign(_h=t.tipo.str.endswith("_historico")).sort_values(["_h", "_v", "chave"], ascending=[True, False, True])
    return t.head(TOP)


def _tile(label: str, value: str, sub: str, color: str) -> str:
    return (f'<td valign="top" width="25%" style="padding:10px 12px;background:{SURFACE};border:1px solid {LINE};border-top:3px solid {color};border-radius:8px">'
            f'<div style="font-size:11px;font-weight:700;color:{INK2}">{escape(label)}</div>'
            f'<div style="font-size:20px;font-weight:700;margin:2px 0;color:{INK}">{escape(value)}</div>'
            f'<div style="font-size:11px;color:{MUTED};line-height:1.35">{escape(sub)}</div></td>')


def body(c: dict, lang: str) -> tuple[str, str]:
    """(html, text) of one language's email."""
    pt, h = lang == "pt", headline(c)
    when = span(c["start"], c["end"], lang)
    page = SITE + "mudancas/" + ("?lang=en" if not pt else "")
    feed = SITE + ("feeds/todas.xml" if pt else "feeds/en/all.xml")
    title = f"O que mudou de {when}" if pt else f"What changed, {when}"
    intro = ("Resumo semanal do que os robôs do political-eye registraram nos dados abertos: empresas que entraram ou saíram "
             "das listas de sanções, sinais de alerta novos, grandes pagamentos de emendas e contratos, meses de votação. "
             "Cada item leva à página que o explica." if pt else
             "A weekly summary of what political-eye's jobs recorded in the open data: companies that entered or left the "
             "sanctions lists, new red flags, large amendment payments and contracts, roll-call months. Each item leads to the "
             "page that explains it.")
    out = [f'<p style="margin:0 0 4px;font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:{MUTED}">political-eye</p>',
           f'<h1 style="margin:0 0 8px;font-size:24px;line-height:1.2;font-weight:700;color:{INK}">{escape(title)}</h1>',
           f'<p style="margin:0 0 16px;font-size:14px;line-height:1.55;color:{INK2}">{escape(intro)}</p>']
    text = [title, "=" * len(title), "", intro, ""]

    tiles = [
        (("Listas de sanções" if pt else "Sanctions lists"), num(h["entraram"], lang),
         (f"empresas entraram, {num(h['sairam'], lang)} saíram; pessoas: {num(h['pessoas_entraram'], lang)} entraram, contadas e nunca nomeadas" if pt
          else f"companies entered, {num(h['sairam'], lang)} left; people: {num(h['pessoas_entraram'], lang)} entered, counted and never named"), COLOR["sancoes"]),
        (("Sinais de alerta" if pt else "Red flags"), num(h["sinais"], lang),
         ((f"novos; e {num(h['antigos'], lang)} contratos antigos achados no histórico" if h["antigos"] else "novos; um sinal não é prova de irregularidade") if pt
          else (f"new; and {num(h['antigos'], lang)} older contracts found in the history" if h["antigos"] else "new; a flag is not evidence of an irregularity")),
         COLOR["alertas"]),
        (("Emendas de R$ 5 mi ou mais" if pt else "Amendment payments of R$ 5 M+"), brl(h["emendas_valor"], lang) if h["emendas"] else "R$ 0",
         (f"em {num(h['emendas'], lang)} pagamentos" if pt else f"in {num(h['emendas'], lang)} payments"), COLOR["emendas"]),
        (("Contratos de R$ 100 mi ou mais" if pt else "Contracts of R$ 100 M+"), brl(h["contratos_valor"], lang) if h["contratos"] else "R$ 0",
         (f"em {num(h['contratos'], lang)} contratos publicados" if pt else f"in {num(h['contratos'], lang)} contracts published"), COLOR["pncp"]),
    ]
    out.append('<table role="presentation" width="100%" cellspacing="6" cellpadding="0" style="border-collapse:separate;margin:0 -6px 8px"><tr>'
               + "".join(_tile(*t) for t in tiles) + "</tr></table>")
    text += [f"- {t[0]}: {t[1]} {t[2]}" for t in tiles] + [""]

    if not h["total"]:
        msg = "Nenhuma mudança registrada nesta semana." if pt else "No change recorded this week."
        out.append(f'<p style="margin:16px 0;font-size:14px;color:{INK2}">{escape(msg)}</p>')
        text += [msg, ""]
    for f in FONTES:
        x = c["fontes"].get(f)
        if not x or not len(x["rows"]):
            continue
        meta, rows = x["meta"], x["rows"]
        name, color = meta["nome"][lang], COLOR[f]
        tipos = meta.get("tipos", {})
        summary = SUMMARY[f](rows, lang)
        out.append(f'<h2 style="margin:26px 0 4px;font-size:13px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:{color}">{escape(name)}</h2>'
                   f'<p style="margin:0 0 8px;font-size:15px;font-weight:600;line-height:1.45;color:{INK}">{escape(summary)}</p>')
        text += [name.upper(), summary]
        lines = []
        for r in _top(f, rows).itertuples(index=False):
            d = describe(r, tipos, lang)
            name_html = (f'<a href="{escape(d["url"])}" style="color:{INK};font-weight:600;text-decoration:none">{escape(d["title"])}</a>' if d["named"]
                         else f'<a href="{escape(d["url"])}" style="color:{INK2};font-style:italic;text-decoration:none">{escape(d["title"])}</a>')
            lines.append(f'<tr><td style="padding:8px 0;border-top:1px solid {LINE};font-size:13px;line-height:1.45">'
                         f'<div style="font-size:11px;font-weight:600;color:{MUTED}">{escape(d["label"])}</div>{name_html}'
                         + (f'<div style="font-size:12px;color:{INK2}">{escape(d["detail"])}</div>' if d["detail"] else "")
                         + f'</td><td valign="top" style="padding:8px 0 8px 12px;border-top:1px solid {LINE};font-size:13px;font-weight:700;text-align:right;white-space:nowrap;color:{INK}">{escape(d["value"])}</td></tr>')
            text.append(f"- {d['label']}: {d['title']}" + (f" — {d['detail']}" if d["detail"] else "") + (f" — {d['value']}" if d["value"] else "") + f"\n  {d['url']}")
        out.append(f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse">{"".join(lines)}</table>')
        listed = sum(1 for _ in _top(f, rows).itertuples())
        shown = len(rows) - listed
        more = SITE + f"mudancas/?fonte={f}&dias=7" + ("&lang=en" if not pt else "")
        link = (f"Ver as {num(len(rows), lang)} mudanças desta fonte na página" if pt else f"See all {num(len(rows), lang)} of this source's changes on the page") \
            if shown > 0 else ("Abrir a página de mudanças" if pt else "Open the changes page")
        out.append(f'<p style="margin:8px 0 0;font-size:13px"><a href="{escape(more)}" style="color:{color};font-weight:600">{escape(link)} →</a></p>')
        text += [f"{link}: {more}"]
        nota = (meta.get("nota") or {}).get(lang) or (NOTAS[f][0 if pt else 1] if f in NOTAS else "")
        if nota:
            out.append(f'<p style="margin:6px 0 0;font-size:12px;font-style:italic;color:{MUTED}">{escape(nota)}</p>')
            text.append(nota)
        text.append("")

    how = ("Mudanças registradas nos commits da semana, de segunda a segunda (UTC)." if c["how"] == "git" else "Mudanças datadas na semana.") if pt else \
        ("Changes recorded in the week's commits, Monday to Monday (UTC)." if c["how"] == "git" else "Changes dated in the week.")
    foot = (f"{how} Pessoas punidas são contadas, nunca nomeadas; empresas individuais com nome de pessoa aparecem sem o nome. "
            "Um sinal de alerta não é prova de irregularidade. Enviado toda segunda-feira pelo workflow weekly de "
            "github.com/mbottoni/political-eye." if pt else
            f"{how} Sanctioned people are counted, never named; individual firms named after a person appear without their name. "
            "A red flag is not evidence of an irregularity. Sent every Monday by the weekly workflow of github.com/mbottoni/political-eye.")
    links = [(page, "Página de mudanças" if pt else "What changed page"), (feed, "Feed Atom" if pt else "Atom feed"),
             ("https://github.com/mbottoni/political-eye/blob/main/methodology/mudancas.md", "Metodologia" if pt else "Methodology")]
    out.append(f'<p style="margin:28px 0 6px;padding-top:14px;border-top:1px solid {LINE};font-size:13px">'
               + " · ".join(f'<a href="{escape(u)}" style="color:{INK2}">{escape(t)}</a>' for u, t in links) + "</p>"
               f'<p style="margin:0;font-size:11.5px;line-height:1.5;color:{MUTED}">{escape(foot)}</p>')
    text += [" · ".join(f"{t}: {u}" for u, t in links), "", foot]
    return "\n".join(out), "\n".join(text)


def build(c: dict, lang: str = "pt") -> tuple[str, str, str]:
    """(subject, html, text). ``lang``: pt, en, or both (Portuguese first)."""
    langs = ["pt", "en"] if lang == "both" else [lang if lang in ("pt", "en") else "pt"]
    parts = [body(c, x) for x in langs]
    sep_html = f'<hr style="margin:36px 0;border:0;border-top:2px solid {LINE}">'
    inner = sep_html.join(h for h, _ in parts)
    page = (f'<!doctype html><html lang="{"pt-BR" if langs[0] == "pt" else "en"}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>{escape(subject(c, langs[0]))}</title></head>'
            f'<body style="margin:0;padding:0;background:{PAGE_BG}">'
            f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:{PAGE_BG}"><tr><td align="center" style="padding:24px 12px">'
            f'<table role="presentation" width="640" cellspacing="0" cellpadding="0" style="width:640px;max-width:100%;background:{SURFACE};border:1px solid {LINE};border-radius:12px">'
            f'<tr><td style="padding:24px 28px;font-family:{FONT};color:{INK}">{inner}</td></tr></table></td></tr></table></body></html>')
    return subject(c, langs[0]), page, ("\n\n" + "-" * 40 + "\n\n").join(t for _, t in parts)


# ------------------------------------------------------------------ send

def send(subject_: str, html_body: str, text: str, out_dir: Path) -> bool:
    """Send if SMTP_USER, SMTP_PASSWORD and EMAIL_TO are set; else dry run. The rendered email is always written to
    ``out_dir`` (CI keeps it as an artifact)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "email.html").write_text(html_body)
    (out_dir / "email.txt").write_text(f"Subject: {subject_}\n\n{text}\n")
    user, password, to = (os.environ.get(k, "").strip() for k in ("SMTP_USER", "SMTP_PASSWORD", "EMAIL_TO"))
    if not (user and password and to):
        print(f"[email] dry run: SMTP_USER / SMTP_PASSWORD / EMAIL_TO not set; wrote {out_dir / 'email.html'}")
        return False
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject_, user, to
    msg.set_content(text)
    msg.add_alternative(html_body, subtype="html")
    host, port = os.environ.get("SMTP_HOST", "smtp.gmail.com"), int(os.environ.get("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=60) as s:
        s.starttls(context=ssl.create_default_context())
        s.login(user, password)
        s.send_message(msg)
    print(f"[email] sent to {len(to.split(','))} recipient(s), {len(msg.as_bytes()) // 1024} KB")
    return True


def run(data: Path, today: date, out_dir: Path, lang: str = "pt") -> bool:
    c = collect(data, today)
    s, h, t = build(c, lang)
    print(f"[email] {c['start']} to {c['end']} ({c['how']}): {headline(c)['total']} changes; {s}")
    return send(s, h, t, out_dir)
