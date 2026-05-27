# LampSmartOpen

> **This fork** adds fast pre-computed packet scripts, multi-lamp support, and a network relay mode for range extension via Raspberry Pi.

LampSmartOpen is an open-source reimplementation of the **LampSmart Pro** control logic.
It allows you to drive compatible BLE lamps directly from a Linux machine using standard tools like `btmgmt`, without the vendor's Android app or cloud.

> ⚠️ This project is **experimental** and targeted at developers / hackers who are comfortable with BLE, Linux, and reverse-engineering. Use at your own risk.

---

## What This Fork Adds

The upstream project provides the core protocol implementation. This fork adds convenience scripts and workflows born from real-world use with 4 lamps across multiple rooms.

### ⚡ Fast Pre-Computed Packets

`lampctrl.sh` computes the BLE advertising payload on every invocation — which works but takes ~5 seconds. That's too slow for binding (lamps only listen for ~5s after power-on).

- **`fast-bind.sh`** — Fires a pre-computed bind packet in ~0.15s. Power-cycle your lamp, run this, done.
- **`fast-lamp.sh`** — Instant on/off/dim with pre-computed packets. `./fast-lamp.sh on`, `./fast-lamp.sh off`, `./fast-lamp.sh dim 128 64`
- **`compute-packets.sh`** — Regenerates pre-computed packets if the lamp UUID changes.

### 🌐 Network Relay (Range Extension)

If your BLE adapter can't reach all lamps, run a Raspberry Pi (or any Linux box) closer to them:

- **`relay.py`** — Tiny HTTP server that receives BLE advertising payloads and broadcasts them via `btmgmt`
- **`send-relay.sh`** — NUC-side sender: `./send-relay.sh pi3b.local on`
- **`pi-setup.sh`** — One-shot Raspberry Pi configuration (SSH in, run it, reboot — done)
- **`ble-relay.service`** — Systemd unit for auto-start on boot

```text
NUC ──HTTP POST──▶ Pi 3B ──btmgmt BLE──▶ 💡 Lamps
```

### 🔗 Upstream

This is a fork of **[AuroraRAS/LampSmartOpen](https://github.com/AuroraRAS/LampSmartOpen)** (GPL-3.0).
All credit for the protocol reverse-engineering and core `lampctrl` binary goes to AuroraRAS.
The `opencodeV3` submodule implements the V3 protocol family.

---

## Quick Start (Fork Edition)

```bash
# 1. Build
git clone --recurse-submodules https://github.com/azolkipli-personal/LampSmartOpen.git
cd LampSmartOpen
cmake -S . -B build && cmake --build build

# 2. Set your lamp UUID
echo '{"lu":"your-uuid-here"}' > .env

# 3. Generate pre-computed packets
./compute-packets.sh

# 4. Bind a lamp (power-cycle it first!)
./fast-bind.sh

# 5. Control
./fast-lamp.sh on
./fast-lamp.sh off
./fast-lamp.sh dim 128 64
```

---

## Features

* **Local control only** – No cloud, no vendor app, just your own Linux box.
* **Reimplementation of the LampSmart Pro protocol** (V3 family).
* **Small C core** that generates the BLE advertising payload.
* **Shell wrapper (`lampctrl.sh`)** that:

  * Computes the lamp control address from a UUID stored in `.env`
  * Uses `btmgmt` to send a single BLE advertising burst
* Designed to be **readable, hackable, and reproducible**.

---

## Repository Layout

The repository is intentionally minimal:

* `.env`
  Local configuration (lamp identifiers etc.), read by the shell wrapper via `jq`.

* `lampctrl.sh`
  Convenience script wrapping `btmgmt` and the `lampctrl` binary.
  It:

  * Extracts the lamp’s UUID from `.env`
  * Derives a control address from UUID fields
  * Calls `lampctrl` to generate the advertising payload
  * Enables LE advertising via `btmgmt`, sends one burst, and stops

* `main.c`
  Command-line tool (`lampctrl`) that generates the LampSmart BLE V3 payload for a given address and operation.

* `CMakeLists.txt`
  Build configuration for the `lampctrl` binary (and any linked encoder libraries / submodules).

* `.gitmodules`
  Submodules used by the encoder / helper code (protocol implementation lives there).

* `LICENSE`
  GPL-3.0 license.

---

## How It Works (High-Level)

The original LampSmart Pro Android app talks to the lamp by broadcasting specially-crafted **BLE advertising packets**, instead of maintaining a classic GATT connection.

LampSmartOpen reconstructs that behaviour:

1. You provide a lamp UUID in `.env`.
2. `lampctrl.sh`:

   * Parses the UUID, extracts the middle fields (e.g. `"27c7-500e"`),
   * Treats them as a 32-bit value, adds 1, and formats it as `0xXXXXXXXX`,
   * Passes that address to `lampctrl` with an operation code.
3. `lampctrl`:

   * Implements the LampSmart V3 command format and encoder.
   * Outputs one or more advertising payloads for `btmgmt`.
4. `btmgmt`:

   * Enables LE, sets the advertising data, advertises briefly, then stops.

This mirrors what the vendor app does, but with transparent, auditable code.

---

## Requirements

To build and run LampSmartOpen, you’ll need:

* A **Linux** system with:

  * A BLE-capable adapter supported by **BlueZ**
  * `btmgmt` (usually provided by the `bluez` package)
* Build toolchain:

  * `cmake`
  * `gcc` or another C compiler
  * `make` or Ninja, depending on how you invoke CMake
* Runtime tools:

  * `jq` (to parse `.env`)

You’ll also need:

* A compatible **LampSmart Pro** lamp
* Basic familiarity with BLE advertising on Linux

---

## Building

Clone the repository (with submodules) and build the C binary:

```bash
git clone --recurse-submodules https://github.com/AuroraRAS/LampSmartOpen.git
cd LampSmartOpen

# Configure build directory
cmake -S . -B build

# Build the lampctrl binary
cmake --build build
```

Depending on your IDE or generator, the resulting binary may be located in something like:

* `build/lampctrl`, or
* `build/Desktop-Debug/lampctrl` (IDE-generated build tree)

Make sure `lampctrl.sh` points to the correct path for your build.

---

## Configuration (`.env`)

The project uses a local `.env` file (JSON format) to store your lamp’s identifiers.

Example:

```json
{
  "lu": "89815eb1-27c7-500e-9d7f-d147a47ce477"
}
```

In `lampctrl.sh`:

* `lu` is read via `jq`
* The script extracts the 2nd and 3rd UUID groups (`27c7-500e` in the example)
* These hex chunks are concatenated (`27c7500e`), interpreted as a 32-bit integer, and incremented by 1
* The result becomes the **control address** passed as `-a` to `lampctrl`, formatted like `0x27c7500f`

You can adjust `.env` if you have multiple lamps or different identifiers. At the moment, the script assumes one primary lamp UUID.

---

## Usage

### 1. Prepare Bluetooth

You typically need `sudo` to talk to `btmgmt`:

```bash
sudo btmgmt --index 0 power on
sudo btmgmt --index 0 le on
```

The script will also perform those steps automatically for its short burst, but it’s useful to verify that your adapter is working first.

### 2. Basic Control via `lampctrl.sh`

After building `lampctrl` and configuring `.env`, you can run:

```bash
./lampctrl.sh
```

The default script behaviour:

* Uses `IDX=0` (first Bluetooth controller)
* Reads `.env` for `lu`
* Computes the address
* Calls something like:

```bash
./build/Desktop-Debug/lampctrl -a 0x27c7500f -o 1
```

* Sets an LE advertisement with the returned data via `btmgmt add-adv`
* Advertises briefly (`-D 2` etc.), clears advertising, and powers LE off again

You can edit `lampctrl.sh` to:

* Change the adapter index (`IDX`)
* Use different operation codes (`-o`) for other actions (e.g. off, dimming, etc.)
* Change advertising duration

### 3. Direct CLI Use (`lampctrl`)

If you want to bypass the shell wrapper and call the encoder directly:

```bash
./build/lampctrl -a 0x27c7500f -o 1
```

The exact options and supported operations are defined in `main.c`.
Typical parameters include at least:

* `-a <address>` – 32-bit control address derived from the lamp UUID
* `-o <opcode>` – numeric operation code (e.g. 1 might represent “turn on”)

You can inspect / extend `main.c` to add more user-friendly commands (e.g. `--on`, `--off`, `--brightness`, etc.).

---

## Development Notes

* The project is GPL-3.0, so **modifications and redistributions must remain open-source**.
* The code aims to be a clean, human-readable representation of the protocol, not just a decompiler dump.
* Contributions that:

  * clean up the encoder,
  * add safer interfaces,
  * or support more lamp models
    are very welcome.

---

## Safety & Legal

* **Trademarks**: “LampSmart” / “LampSmart Pro” are likely trademarks of their respective owner. This project is not affiliated with or endorsed by them.
* **Electrical safety**: You are ultimately controlling mains-powered lighting. Don’t use this to automate anything that could cause fire risk or other hazards.

---

## License

This project is licensed under the **GNU General Public License v3.0**.
See the [`LICENSE`](LICENSE) file for details.

---

# LampSmartOpen

LampSmartOpen は **LampSmart Pro** の制御ロジックをオープンソースで再実装したプロジェクトです。
Linux マシンから `btmgmt` など標準的なツールだけで BLE ランプを制御でき、ベンダーの Android アプリやクラウドは不要です。

> ⚠️ このプロジェクトは **実験的** で、BLE・Linux・リバースエンジニアリングに慣れている開発者／ハッカー向けです。利用は自己責任でお願いします。

---

## 特長

* **完全ローカル制御** — クラウドもアプリも不要
* **LampSmart Pro（V3系）のプロトコル実装**
* **小さくシンプルな C コア実装**（BLE Advertising Payload生成ツール）
* **シェルラッパー `lampctrl.sh`**

  * `.env` の UUID から制御アドレスを計算
  * `btmgmt` を使って BLE Advertising を 1 回だけ送信
* **読みやすく、変更しやすく、再現可能**

---

## リポジトリ構成

* `.env`
  UUID などローカル設定（`jq` で読み取る）

* `lampctrl.sh`
  `lampctrl` バイナリと `btmgmt` を包むシェルスクリプト

  * `.env` から UUID を抽出
  * UUID の一部から制御アドレスを生成
  * `lampctrl` を呼び出しペイロード生成
  * `btmgmt` で Advertising を短時間送信

* `main.c`
  コマンドラインツール `lampctrl` の実装。
  LampSmart V3 のペイロードを生成。

* `CMakeLists.txt`
  `lampctrl` のビルド設定。

* `.gitmodules`
  エンコーダ関係のサブモジュール。

* `LICENSE`（GPL-3.0）

---

## 仕組み（概要）

LampSmart Pro アプリは、GATT 接続ではなく、特別な **BLE Advertising パケット** を連続送信する方式でランプを制御している。

LampSmartOpen はその挙動を再現する。

1. `.env` にランプの UUID を記述
2. `lampctrl.sh` が:

   * UUID の第2・第3フィールド（例: `27c7-500e`）を抽出
   * 連結して 32bit 数値に変換し +1
   * それを `lampctrl` に `-a` として渡す
3. `lampctrl` が:

   * LampSmart V3 コマンドを構築
   * `btmgmt add-adv` 用の Advertising データを出力
4. `btmgmt` が:

   * LE をオンにし、広告データをセット
   * 2 秒程度広告したあと停止

Android アプリがしていることを透明かつシンプルに再現しているだけの構造。

---

## 必要環境

* **Linux**

  * BLE 対応アダプタ（BlueZ サポート）
  * `btmgmt`（BlueZ パッケージに含まれる）
* ビルドツール

  * `cmake`
  * `gcc`（または対応する C コンパイラ）
  * `make` または Ninja
* コマンドラインツール

  * `jq`（`.env` 読み取り用）

必須ではないが、以下があると便利:

* LampSmart Pro 対応ランプ
* BLE Advertising の基礎知識

---

## ビルド方法

サブモジュール込みで clone。

```bash
git clone --recurse-submodules https://github.com/AuroraRAS/LampSmartOpen.git
cd LampSmartOpen

cmake -S . -B build
cmake --build build
```

`lampctrl` は IDE によって以下のような場所に出力されることがある：

* `build/lampctrl`
* `build/Desktop-Debug/lampctrl`

`lampctrl.sh` 内のパスを適宜調整すること。

---

## `.env` の設定

`.env` は JSON 形式で設定を書く。

例:

```json
{
  "lu": "89815eb1-27c7-500e-9d7f-d147a47ce477"
}
```

スクリプトは:

* 第2・第3フィールド (`27c7-500e`) を抽出
* 16進数を連結 → `27c7500e`
* 32bit として +1 → `0x27c7500f`
* それを制御アドレスとして `lampctrl -a` に渡す

複数ランプを扱う場合は `.env` を複数管理しても良い。現状は単一 UUID を想定。

---

## 使い方

### 1. Bluetooth の準備

事前確認として:

```bash
sudo btmgmt --index 0 power on
sudo btmgmt --index 0 le on
```

`lampctrl.sh` 自体もこれらを内部で行うが、動作確認のため手動で試す価値がある。

### 2. シェルスクリプトから制御

ビルド後、単純に:

```bash
./lampctrl.sh
```

デフォルト挙動:

* `.env` から UUID を読み取り
* 制御アドレス算出
* 例として:

```bash
./build/Desktop-Debug/lampctrl -a 0x27c7500f -o 1
```

* `btmgmt add-adv` にペイロードを渡して広告
* 数秒で広告停止

`lampctrl.sh` を編集すれば:

* Bluetooth アダプタ index (`IDX`)
* 操作コード (`-o`)
* 広告時間

など自由に変更できる。

### 3. `lampctrl` を直接使う

```bash
./build/lampctrl -a 0x27c7500f -o 1
```

サポートされるオプションは `main.c` に定義されている。
基本は:

* `-a <address>` — 制御アドレス
* `-o <opcode>` — 操作コード（点灯/消灯/調光など）

必要に応じて `--on`, `--off` など分かりやすいラッパーを追加できる。

---

## 開発に関するメモ

* GPL-3.0 のため、改変・再配布は同ライセンスで公開が必要
* コードは「デコンパイル結果をそのまま並べたもの」ではなく、可読性を重視
* エンコーダの整理や追加モデルの対応などのコントリビュートは歓迎

---

## 安全性・法的注意

* 「LampSmart」「LampSmart Pro」はそれぞれの権利者の商標であり、当プロジェクトは非公式
* 制御対象は AC 電源に接続された照明器具であり、誤操作による危険に注意

---

## ライセンス

本プロジェクトは **GNU GPL v3.0** で公開されています。
詳細は `LICENSE` を参照してください。

