import typer

from kokoro_cli import __version__
from kokoro_cli import live, profile, setup, tts
from kokoro_cli.voices import list_voices

app = typer.Typer(
    name="kokoro",
    help="Local Kokoro-82M text-to-speech CLI.",
    no_args_is_help=True,
    invoke_without_command=True,
    rich_markup_mode="rich",
)
app.command("tts")(tts.run)
app.command("live")(live.run)
app.command("profile")(profile.run)


@app.command()
def voices() -> None:
    """List available voices."""
    all_voices = list_voices()
    if not all_voices:
        raise SystemExit("No voices found. Run `kokoro install` to download them.")
    typer.echo(f"{len(all_voices)} voices in Kokoro-82M/voices:")
    for name in all_voices:
        typer.echo(f"  {name}")


@app.command()
def install(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the download confirmation"),
) -> None:
    """Download the Kokoro-82M model + voices (md5-verified)."""
    setup.download_weights(confirmed=yes)


@app.command()
def uninstall(
    force: bool = typer.Option(False, "--force", "-f", help="Skip the removal confirmation"),
) -> None:
    """Remove downloaded model data (weights + voices)."""
    setup.uninstall(force=force)


@app.command()
def doctor() -> None:
    """Show where the model lives and whether it's complete."""
    setup.doctor()


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", help="Show version and exit"),
) -> None:
    if version:
        typer.echo(f"kokoro {__version__}")
        raise typer.Exit()
