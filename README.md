# SBC ライセンス生成ツール

Smart Bed Control System（SBC）向けに、顧客から受け取った `installation_request.json` をもとに署名済み `license.json` を発行する、**開発者専用**の CLI ツールです。

Backend リポジトリとは独立しており、**秘密鍵はこのツールを実行する開発者のローカル環境のみ**で管理します。Backend の起動処理からは呼び出しません。

## ディレクトリ構成

```
sbc_license_generate/
├── generate_license.py      # ライセンス生成スクリプト
├── license_constants.py     # 署名定数（Backend と同期必須）
├── requirements.txt
├── installation_request/    # サンプル・受領用 installation_request.json
└── license_file/            # 生成した license.json の出力先（例）
```

## セットアップ

```bash
cd sbc_license_generate
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux / macOS
pip install -r requirements.txt
```

## 使い方

**コマンドは 1 行で実行**してください。複数行の `\` 継続を使うと `--output` が `li` などに切れ、`license.json` 以外のファイル名で出力されることがあります。

```bash
python generate_license.py --request ./installation_request/installation_request.json --private-key private_key.pem --customer "Example Hospital" --license-id "SBC-2026-0001" --output ./license_file/license.json
```

暗号化 PEM（`BEGIN ENCRYPTED PRIVATE KEY`）の場合は、パスワードを次のいずれかで指定します。

```bash
python generate_license.py --request ./installation_request/installation_request.json --private-key private_key.pem --private-key-password "Gmizushi777!" --customer "Example Hospital" --license-id "SBC-2026-0001" --output ./license_file/license.json
```

成功時の出力例:

```
License generated successfully.
  Output:        license_file\license.json
  Customer:      Example Hospital
  License ID:    SBC-2026-0001
  Installation:  b51821b8...
```

### 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `--request` | はい | 顧客環境で生成された `installation_request.json` のパス |
| `--private-key` | はい | 署名用 `private_key.pem` のパス（リポジトリに含めない） |
| `--customer` | はい | 導入先病院名（表示用） |
| `--license-id` | はい | ライセンス ID（例: `SBC-2026-0001`） |
| `--output` | はい | 出力先。**ファイル名は `license.json` 必須** |
| `--private-key-password` | いいえ | 暗号化 PEM のパスワード |

パスワードの指定方法（暗号化 PEM の場合）:

1. `--private-key-password "（パスワード）"`
2. 環境変数 `SBC_PRIVATE_KEY_PASSWORD`
3. 未指定時は対話入力（`Private key password:`）

## 入出力ファイル

### installation_request.json（入力）

Backend が初回起動時に生成します。主なフィールド:

| フィールド | 説明 |
|------------|------|
| `product` | 製品名（`Smart Bed Control System` であること） |
| `installation_id` | 環境固有 ID（署名対象） |
| `generated_at` | 生成日時 |
| `license_required` | ライセンス要否 |

### license.json（出力）

| フィールド | 説明 |
|------------|------|
| `product` | 製品名 |
| `license_id` | 発行したライセンス ID |
| `customer` | 導入先病院名 |
| `installation_id` | 入力リクエストから引き継ぎ |
| `issued_by` | 発行者名 |
| `signature` | RSA-PSS（SHA-256）による Base64 署名 |

## 秘密鍵・公開鍵の初回生成

開発者ローカルのみで実行します。

```bash
openssl genrsa -out private_key.pem 2048
openssl rsa -in private_key.pem -pubout -out public_key.pem
```

発行した `public_key.pem` を Backend の `sbc_dev/backend/sbc_license/public_key.pem` に配置してください（Git 管理対象）。

`private_key.pem` は `.gitignore` 対象です。暗号化 PEM を使う場合は、作成時に設定したパスワードを安全に保管してください。

## オンプレ本番での発行フロー

1. 顧客が Backend を初回起動 → `installation_request.json` が生成される
2. 顧客が `installation_request.json` を KOTOBUKI Digital Science Lab. に送付
3. 本ツールで `license.json` を発行
4. 顧客が `license.json` を `sbc_license/` に配置し Backend を再起動

## Docker 開発環境での注意

Backend が Linux コンテナ内で動作している場合、**license 発行も同じコンテナ内で行う**必要があります。ホスト（Windows）上で発行すると `installation_id` が一致せず検証に失敗します。

コンテナにツールをコピーして実行する例:

```bash
docker cp sbc_license_generate sbc_dev-backend-1:/tmp/sbc_license_generate
docker exec -it sbc_dev-backend-1 pip install -r /tmp/sbc_license_generate/requirements.txt
docker exec -it sbc_dev-backend-1 python /tmp/sbc_license_generate/generate_license.py --request /app/sbc_license/installation_request.json --private-key /tmp/private_key.pem --private-key-password "（パスワード）" --customer "Example Hospital" --license-id "SBC-2026-0001" --output /app/sbc_license/license.json
```

`private_key.pem` はコンテナに `docker cp` で渡すか、開発用ボリュームマウントで参照してください。本番ではコンテナ外の開発者マシンから発行し、生成した `license.json` のみを顧客に渡します。

## Backend との同期

`license_constants.py` の `PRODUCT_NAME`・`ISSUED_BY`・`canonical_json()` は Backend の `app/core/license.py` と**同一**である必要があります。変更時は両方を更新してください。

署名方式も Backend と一致しています:

- アルゴリズム: RSA-PSS + SHA-256
- 正規化: `signature` フィールドを除いた JSON をキーソート・コンパクト形式でシリアライズ

## セキュリティ

- `private_key.pem` は絶対に Git にコミットしない（`.gitignore` 済み）
- パスワードや秘密鍵を README・コマンド履歴・ログに残さない
- 本ツールは Backend 起動処理から呼び出さない
- 顧客には `license.json` のみを渡し、秘密鍵は共有しない
