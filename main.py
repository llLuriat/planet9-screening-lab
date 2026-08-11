"""Ponto de entrada único do projeto. Rode `python main.py doctor` primeiro
se não tiver certeza de que o ambiente está configurado corretamente."""
import sys


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "doctor":
        # Caso especial: NÃO importa planet9lab.cli aqui, porque cli.py
        # importa planet9lab.run -> planet9lab.engine -> planet9lab.schemas,
        # que precisa de pydantic instalado. Se for exatamente isso que
        # está faltando, 'doctor' precisa continuar funcionando para dizer
        # isso claramente, em vez de morrer com um traceback antes de
        # imprimir qualquer coisa.
        from planet9lab.doctor import run_doctor

        return run_doctor()

    try:
        from planet9lab.cli import main as cli_main
    except ImportError as exc:
        print(f"Erro ao carregar o pipeline (dependência ausente ou quebrada): {exc}")
        print("Rode 'python main.py doctor' para diagnosticar o ambiente.")
        return 1
    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
