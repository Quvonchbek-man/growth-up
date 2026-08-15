"""Butunlik tekshiruvlari — "jimgina" nosozliklarni ushlaydi.

Bu yerdagi xatolar odatda faqat ishlab chiqarishda, foydalanuvchi tugmani
bosganda ko'rinadi: import xatosi, matndagi yetishmagan `{name}`, yo'q
matnga murojaat. Ikkalasi ham bir necha kun sezilmasligi mumkin.
"""

from __future__ import annotations

import ast
import importlib
import pathlib
import string

import pytest

PROJECT = pathlib.Path(__file__).parent.parent
PAKETLAR = ["api", "bot", "services", "shared", "scripts"]
LOCALES = PROJECT / "bot" / "locales" / "uz.py"


def _modul_fayllari() -> list[pathlib.Path]:
    fayllar: list[pathlib.Path] = []
    for paket in PAKETLAR:
        fayllar += sorted((PROJECT / paket).rglob("*.py"))
    return [f for f in fayllar if "__pycache__" not in f.parts]


def _modul_nomi(path: pathlib.Path) -> str:
    nisbiy = path.relative_to(PROJECT).with_suffix("")
    qismlar = list(nisbiy.parts)
    if qismlar[-1] == "__init__":
        qismlar.pop()
    return ".".join(qismlar)


@pytest.mark.parametrize("path", _modul_fayllari(), ids=_modul_nomi)
def test_har_bir_modul_import_bolinadi(path):
    """Sintaksis yoki import xatosi bo'lsa, shu yerda ko'rinadi."""
    importlib.import_module(_modul_nomi(path))


def test_run_py_import_bolinadi():
    """Kirish nuqtasi ham buzuq bo'lmasin (`__main__` qo'riqchisi bor)."""
    importlib.import_module("run")


# ─── Matn shablonlari ────────────────────────────────────────────────────────


def _locale_konstantalari() -> dict[str, object]:
    """`uz.py` dagi barcha konstantalar — satrlar ham, ro'yxatlar ham."""
    tree = ast.parse(LOCALES.read_text(encoding="utf-8"))
    natija: dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            natija[target.id] = ast.literal_eval(node.value)
        except (ValueError, SyntaxError):
            continue
    return natija


def _locale_matnlari() -> dict[str, str]:
    """Faqat satr konstantalar (`{...}` tekshiruvi uchun)."""
    return {k: v for k, v in _locale_konstantalari().items() if isinstance(v, str)}


def _joy_egalari(matn: str) -> set[str]:
    return {
        name.split(".")[0].split("[")[0]
        for _, name, _, _ in string.Formatter().parse(matn)
        if name
    }


def _format_chaqiruvlari() -> list[tuple[str, str, set[str], int, bool]]:
    """Kodda uchraydigan `T.NOM.format(...)` chaqiruvlari.

    Qaytaradi: (fayl, matn nomi, berilgan kalitlar, qator, yulduzli).

    `yulduzli` — chaqiruvda `**lugat` ishlatilgani. Bunday holatda kalitlarni
    statik tekshirib bo'lmaydi, ya'ni bu tekshiruv o'sha matn uchun ishlamay
    qoladi. Shuning uchun uni ruxsat berish emas, **xato deb** hisoblaymiz.
    """
    chaqiruvlar = []
    for path in _modul_fayllari():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr == "format"):
                continue
            egasi = func.value
            if not (
                isinstance(egasi, ast.Attribute)
                and isinstance(egasi.value, ast.Name)
                and egasi.value.id == "T"
            ):
                continue
            kalitlar = {kw.arg for kw in node.keywords if kw.arg}
            yulduzli = any(kw.arg is None for kw in node.keywords)
            chaqiruvlar.append(
                (
                    str(path.relative_to(PROJECT)),
                    egasi.attr,
                    kalitlar,
                    node.lineno,
                    yulduzli,
                )
            )
    return chaqiruvlar


def test_locale_fayli_oqiladi():
    matnlar = _locale_matnlari()
    assert len(matnlar) > 30, "matnlar topilmadi — ajratuvchi buzilgan bo'lishi mumkin"
    assert "START_NEW" in matnlar


def test_format_kalitlari_matnga_mos():
    """`T.X.format(...)` matndagi barcha `{...}` larni to'ldirishi shart.

    Yetishmasa — `KeyError`, ya'ni bot o'sha paytda jim qoladi.
    """
    matnlar = _locale_matnlari()
    xatolar = []

    for fayl, nom, berilgan, qator, yulduzli in _format_chaqiruvlari():
        if nom not in matnlar:
            xatolar.append(f"{fayl}:{qator} — T.{nom} umuman yo'q")
            continue
        if yulduzli:
            xatolar.append(
                f"{fayl}:{qator} — T.{nom}.format(**lugat): kalitlarni "
                "tekshirib bo'lmaydi. Ochiq yozing (kalit=qiymat), aks holda "
                "matnga yangi {kalit} qo'shilsa xato faqat ishlab chiqarishda "
                "bilinadi"
            )
            continue
        kerak = _joy_egalari(matnlar[nom])
        yetishmagan = kerak - berilgan
        ortiqcha = berilgan - kerak
        if yetishmagan:
            xatolar.append(f"{fayl}:{qator} — T.{nom} uchun yetishmadi: {sorted(yetishmagan)}")
        if ortiqcha:
            xatolar.append(f"{fayl}:{qator} — T.{nom} ga ortiqcha berildi: {sorted(ortiqcha)}")

    assert not xatolar, "Matn shablonlari mos emas:\n" + "\n".join(xatolar)


def _ishlatilgan_nomlar() -> set[str]:
    """Kodda `T.NOM` ko'rinishida murojaat qilingan nomlar."""
    nomlar: set[str] = set()
    for path in _modul_fayllari():
        if path.name == "uz.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "T"
            ):
                nomlar.add(node.attr)
    return nomlar


def test_ishlatilgan_matnlar_mavjud():
    """Kodda `T.NOM` deb yozilgan har bir nom `uz.py` da bo'lishi kerak.

    Bo'lmasa — `AttributeError`, ya'ni handler o'sha paytda ishlamay qoladi.
    """
    mavjud = set(_locale_konstantalari())
    yoq = sorted(_ishlatilgan_nomlar() - mavjud)
    assert not yoq, f"Mavjud bo'lmagan matnga murojaat: {yoq}"


# Yozilgan, lekin hali ulanmagan matnlar. Har biri — kichik bo'shliq, xato
# emas. Ro'yxat ataylab shu yerda: yangi "o'lik" matn qo'shilsa test darhol
# aytadi, bularni esa ulash yoki o'chirish kerakligini unutmaymiz.
ULANMAGAN_MATNLAR = {
    # Streak uzilganini foydalanuvchiga hech kim aytmaydi (`streak.py` faqat
    # hisoblaydi). Ilovaning asosiy mexanikasi — aytilsa ta'siri kuchayadi.
    "STREAK_LOST",
    # Bot notanish xabarga umuman javob bermaydi — foydalanuvchi yozadi,
    # javob yo'q, "buzilgan" deb o'ylaydi.
    "UNKNOWN_COMMAND",
    # ✅ dan qaytarish tugmasi: hozir ✅ ni qayta bosish orqali ishlaydi
    "BTN_UNDO",
    # Allaqachon a'zo bo'lgan odamga `JOIN_OK` ko'rsatiladi
    "JOIN_ALREADY",
    # A'zo chiqarilgach sardorga botdan tasdiq bormaydi (ilova o'zi ko'rsatadi)
    "MEMBER_REMOVED",
}


def test_olik_matn_qolmagan():
    """Ishlatilmaydigan matnlar faqat ma'lum ro'yxatdagilar bo'lishi kerak.

    Yangisi paydo bo'lsa — yo matn ortiqcha, yo uni ishlatadigan kod
    tushib qolgan. Ikkalasi ham bilinishi kerak.
    """
    olik = set(_locale_konstantalari()) - _ishlatilgan_nomlar()
    yangi = sorted(olik - ULANMAGAN_MATNLAR)
    assert not yangi, f"Yangi ishlatilmaydigan matn paydo bo'ldi: {yangi}"

    tuzatilgan = sorted(ULANMAGAN_MATNLAR - olik)
    assert not tuzatilgan, (
        f"Bu matnlar endi ishlatilyapti — ULANMAGAN_MATNLAR dan olib tashlang: {tuzatilgan}"
    )


# ─── Bot yig'ilishi ──────────────────────────────────────────────────────────


def test_dispatcher_yigiladi():
    """Handlerlar, filtrlar va middleware'lar bir-biriga mos ekanini tekshiradi."""
    from bot.main import build_bot, build_dispatcher

    bot = build_bot()
    dp = build_dispatcher()
    assert bot is not None
    assert dp is not None


def test_klaviaturalar_yigiladi():
    from bot import keyboards as kb
    from shared.models import Task, TaskStatus

    assert kb.main_menu() is not None
    assert kb.plan_tomorrow() is not None
    assert kb.reason_choices(1) is not None

    task = Task(id=1, title="Sinov", status=TaskStatus.PLANNED, points=1)
    assert kb.day_tasks([task]) is not None
