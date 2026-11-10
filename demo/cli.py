"""Command line entry point for the demo pack."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from . import __version__
from .config import data_root, input_root, output_root, scenario_output
from .generators import mergado_feeds, shoptet_orders, supplier_invoices
from .scenarios import invoices_to_pohoda, mergado_feed, shoptet_to_pohoda
from .util import ensure_dir, reset_dir, write_json

SCENARIOS = {
    "shoptet": shoptet_to_pohoda.run,
    "invoices": invoices_to_pohoda.run,
    "mergado": mergado_feed.run,
}

console = Console()


def _data_dir(args) -> Path:
    return Path(args.data_dir).resolve() if getattr(args, "data_dir", None) else data_root()


def generate(data_dir: Path | None = None) -> dict:
    root = data_dir or data_root()
    result = {
        "shoptet": shoptet_orders.generate(root / "input" / "shoptet"),
        "invoices": supplier_invoices.generate(root / "input" / "invoices"),
        "mergado": mergado_feeds.generate(root / "input" / "mergado"),
    }
    return result


def _check_inputs(data_dir: Path) -> None:
    required = [
        data_dir / "input" / "shoptet" / "orders.json",
        data_dir / "input" / "shoptet" / "catalog.json",
        data_dir / "input" / "invoices" / "catalog.json",
        data_dir / "input" / "mergado" / "supplier_a.xml",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Chýbajú vstupy. Najprv spustite `python -m demo generate`.\n" + "\n".join(missing)
        )


def run_scenario(name: str, data_dir: Path | None = None) -> dict:
    root = data_dir or data_root()
    _check_inputs(root)
    return SCENARIOS[name](root)


def _print_summary(results: list[dict]) -> None:
    table = Table(title="perepolkin.sk · Shoptet/Pohoda demo")
    table.add_column("Scenár")
    table.add_column("Vstup", justify="right")
    table.add_column("Spracované", justify="right")
    table.add_column("Na kontrolu", justify="right")
    table.add_column("Ticho prejdené", justify="right")
    for result in results:
        report = result["report"]
        table.add_row(
            report["title"],
            str(report["input_count"]),
            str(report["processed"]),
            str(report["flagged"]),
            str(report["silent_errors"]),
        )
    console.print(table)


def command_generate(args) -> int:
    result = generate(_data_dir(args))
    console.print("[bold]Vstupy vygenerované:[/bold]")
    for name, info in result.items():
        console.print(f"  {name}: {info}")
    return 0


def command_run(args) -> int:
    result = run_scenario(args.scenario, _data_dir(args))
    _print_summary([result])
    console.print(f"Report: [cyan]{result['output_dir'] / 'report.md'}[/cyan]")
    return 0


def command_run_all(args) -> int:
    root = _data_dir(args)
    reset_dir(root / "output")
    generate(root)
    results = []
    for name in ("shoptet", "invoices", "mergado"):
        console.rule(f"[bold]{name}[/bold]")
        results.append(run_scenario(name, root))
    _print_summary(results)
    summary = {
        "generated_at": "2026-11-10T10:00:00Z",
        "scenarios": [
            {
                "scenario": item["report"]["scenario"],
                "input_count": item["report"]["input_count"],
                "processed": item["report"]["processed"],
                "flagged": item["report"]["flagged"],
                "silent_errors": item["report"]["silent_errors"],
                "report": f"data/output/{item['report']['scenario']}/report.json",
            }
            for item in results
        ],
    }
    write_json(root / "output" / "summary.json", summary)
    failed = [item for item in results if item["report"]["silent_errors"] != 0]
    if failed:
        console.print("[red]Nezhoda v reportoch: silent_errors != 0[/red]")
        return 1
    console.print("[green]Hotovo: 3 scenáre, 0 ticho prejdených chýb.[/green]")
    console.print("[dim]Syntetické dáta. DEMO. Nie je to reálny klient.[/dim]")
    return 0


def command_assets(args) -> int:
    from .artifacts import build_all

    result = build_all(_data_dir(args), make_video=not args.skip_video)
    console.print(f"Screenshoty: [cyan]{result['screenshots']}[/cyan]")
    if result.get("video"):
        console.print(f"Video: [cyan]{result['video']}[/cyan]")
    console.print(f"Handoff: [cyan]{result['handoff']}[/cyan]")
    return 0


def command_pack(args) -> int:
    from .artifacts import build_zip

    path = build_zip(_data_dir(args))
    console.print(f"ZIP: [cyan]{path}[/cyan]")
    return 0


def command_clean(args) -> int:
    root = _data_dir(args)
    reset_dir(root / "output")
    console.print(f"Vyčistené: [cyan]{root / 'output'}[/cyan]")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m demo",
        description="Syntetické Shoptet → Pohoda demo. Žiadna sieť, žiadne reálne dáta.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="vygenerovať syntetické vstupy")
    gen.add_argument("--data-dir", type=Path, help="alternatívny dátový adresár")
    gen.set_defaults(func=command_generate)

    run = sub.add_parser("run", help="spustiť jeden scenár")
    run.add_argument("--scenario", required=True, choices=sorted(SCENARIOS))
    run.add_argument("--data-dir", type=Path, help="alternatívny dátový adresár")
    run.set_defaults(func=command_run)

    run_all = sub.add_parser("run-all", help="vyčistiť, vygenerovať a spustiť všetko")
    run_all.add_argument("--data-dir", type=Path, help="alternatívny dátový adresár")
    run_all.set_defaults(func=command_run_all)

    assets = sub.add_parser("assets", help="vygenerovať screenshoty, video a handoff")
    assets.add_argument("--data-dir", type=Path, help="alternatívny dátový adresár")
    assets.add_argument("--skip-video", action="store_true", help="preskočiť ffmpeg video")
    assets.set_defaults(func=command_assets)

    pack = sub.add_parser("pack", help="zabaliť demo do ZIP")
    pack.add_argument("--data-dir", type=Path, help="alternatívny dátový adresár")
    pack.set_defaults(func=command_pack)

    clean = sub.add_parser("clean", help="vyčistiť data/output")
    clean.add_argument("--data-dir", type=Path, help="alternatívny dátový adresár")
    clean.set_defaults(func=command_clean)
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        return 2


if __name__ == "__main__":
    sys.exit(main())
