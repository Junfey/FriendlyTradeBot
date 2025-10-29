import asyncio
import json
from pathlib import Path
import typer

from exchange.binance import BinanceExchange

app = typer.Typer(help="FriendlyTradeBot CLI")

@app.command()
def check_connection():
    """Быстрая проверка соединения с биржей (цена BTCUSDT)."""
    async def _run():
        ex = BinanceExchange()
        try:
            price = await ex.get_price("BTC/USDT")
            typer.echo(f"OK. BTC/USDT price: {price}")
        finally:
            await ex.close()
    asyncio.run(_run())

@app.command()
def restore(from_path: Path):
    """Восстановить стратегии из бэкапа JSON."""
    from state_manager import save_strategies
    data = json.loads(Path(from_path).read_text("utf-8"))
    if not isinstance(data, dict):
        raise typer.BadParameter("Ожидается JSON-объект со словарём стратегий")
    save_strategies(data)
    typer.secho("Стратегии восстановлены.", fg=typer.colors.GREEN)

@app.command()
def export(to_path: Path = Path("data/export.json")):
    """Экспорт текущих стратегий в JSON."""
    from state_manager import load_strategies
    data = load_strategies()
    to_path.parent.mkdir(parents=True, exist_ok=True)
    to_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.secho(f"Экспортировано в: {to_path}", fg=typer.colors.GREEN)

if __name__ == "__main__":
    app()
