import os

from backend import create_app

if __name__ == "__main__":
    from waitress import serve

    app = create_app()
    port = int(os.getenv("PORT", "5002"))
    print(f"Motel Admin Python: http://127.0.0.1:{port}", flush=True)
    serve(app, host="127.0.0.1", port=port)
