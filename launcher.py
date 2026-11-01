"""Entry point used by the desktop packager."""
from unity_webgl_launcher.app import main

if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == "--smoke-test":
        from unity_webgl_launcher.smoke import run
        raise SystemExit(run(sys.argv[2]))
    main()
