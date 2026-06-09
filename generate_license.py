#!/usr/bin/env python3
"""
開発者向けライセンス生成スクリプト

installation_request.json を読み込み、private_key.pem で署名した license.json を生成する。
Backend 起動処理からは呼び出さないこと。
"""
import argparse
import base64
import getpass
import json
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from license_constants import ISSUED_BY, PRODUCT_NAME, canonical_json

PSS_PADDING = padding.PSS(
    mgf=padding.MGF1(hashes.SHA256()),
    salt_length=padding.PSS.MAX_LENGTH,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="installation_request.json から署名済み license.json を生成する"
    )
    parser.add_argument(
        "--request",
        required=True,
        help="installation_request.json のパス",
    )
    parser.add_argument(
        "--private-key",
        required=True,
        help="private_key.pem のパス",
    )
    parser.add_argument(
        "--customer",
        required=True,
        help="導入先病院名",
    )
    parser.add_argument(
        "--license-id",
        required=True,
        help="ライセンス ID",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="出力先 license.json のパス",
    )
    parser.add_argument(
        "--private-key-password",
        default=None,
        help="暗号化された private_key.pem のパスワード（未指定時は環境変数 SBC_PRIVATE_KEY_PASSWORD または対話入力）",
    )
    return parser.parse_args()


def validate_output_path(output_path: Path) -> None:
    if output_path.name != "license.json":
        print(
            f"Error: --output must end with license.json (got: {output_path})",
            file=sys.stderr,
        )
        print(
            "Hint: コマンドが複数行に分かれるとパスが切れることがあります。"
            "1行で実行するか、--output ./sbc_license/license.json を確認してください。",
            file=sys.stderr,
        )
        sys.exit(1)


def load_request(path: Path) -> dict:
    if not path.exists():
        print(f"Error: request file not found: {path}", file=sys.stderr)
        sys.exit(1)
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def resolve_private_key_password(password_arg: str | None) -> bytes:
    if password_arg is not None:
        return password_arg.encode("utf-8")

    env_password = os.environ.get("SBC_PRIVATE_KEY_PASSWORD")
    if env_password:
        return env_password.encode("utf-8")

    entered = getpass.getpass("Private key password: ")
    if not entered:
        print(
            "Error: private key is encrypted but no password was provided",
            file=sys.stderr,
        )
        sys.exit(1)
    return entered.encode("utf-8")


def load_private_key(path: Path, password: str | None = None):
    if not path.exists():
        print(f"Error: private key file not found: {path}", file=sys.stderr)
        sys.exit(1)
    pem_data = path.read_bytes()

    try:
        return serialization.load_pem_private_key(pem_data, password=None)
    except TypeError:
        key_password = resolve_private_key_password(password)
        try:
            return serialization.load_pem_private_key(pem_data, password=key_password)
        except ValueError:
            print(
                "Error: invalid private key password "
                "(private_key.pem 作成時に設定したパスワードを指定してください)",
                file=sys.stderr,
            )
            sys.exit(1)


def validate_inputs(request: dict, customer: str, license_id: str) -> str:
    if request.get("product") != PRODUCT_NAME:
        print(
            f'Error: request.product must be "{PRODUCT_NAME}"',
            file=sys.stderr,
        )
        sys.exit(1)

    installation_id = request.get("installation_id")
    if not installation_id:
        print("Error: request.installation_id is required", file=sys.stderr)
        sys.exit(1)

    if not customer.strip():
        print("Error: --customer must not be empty", file=sys.stderr)
        sys.exit(1)

    if not license_id.strip():
        print("Error: --license-id must not be empty", file=sys.stderr)
        sys.exit(1)

    return str(installation_id)


def sign_license_payload(payload: dict, private_key) -> str:
    signature = private_key.sign(
        canonical_json(payload),
        PSS_PADDING,
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("ascii")


def build_license(
    installation_id: str,
    customer: str,
    license_id: str,
    private_key,
) -> dict:
    payload = {
        "product": PRODUCT_NAME,
        "license_id": license_id,
        "customer": customer,
        "installation_id": installation_id,
        "issued_by": ISSUED_BY,
    }
    payload["signature"] = sign_license_payload(payload, private_key)
    return payload


def main() -> None:
    args = parse_args()

    request_path = Path(args.request)
    private_key_path = Path(args.private_key)
    output_path = Path(args.output)
    validate_output_path(output_path)

    request = load_request(request_path)
    installation_id = validate_inputs(request, args.customer, args.license_id)
    private_key = load_private_key(
        private_key_path, password=args.private_key_password
    )

    license_data = build_license(
        installation_id=installation_id,
        customer=args.customer,
        license_id=args.license_id,
        private_key=private_key,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(license_data, f, indent=2)
        f.write("\n")

    print("License generated successfully.")
    print(f"  Output:        {output_path}")
    print(f"  Customer:      {args.customer}")
    print(f"  License ID:    {args.license_id}")
    print(f"  Installation:  {installation_id}")


if __name__ == "__main__":
    main()
