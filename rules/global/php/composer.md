---
paths:
  - "**/composer.json"
  - "**/composer.lock"
---

# Composer / 依存管理規約

PHP 8.4 + Laravel 12 プロジェクトの `composer.json` 規約と依存管理ルール。

## バージョン固定

### PHP / Laravel

```json
{
    "require": {
        "php": "^8.4",
        "laravel/framework": "^12.0"
    }
}
```

- PHP は `^8.4` でメジャー固定 + マイナー以上を許容
- Laravel は `^12.0` でメジャー固定。Laravel のメジャーバージョン跨ぎはアップグレード時にリリースノートを確認する

### `composer.lock` のコミット

`composer.lock` は **必ずコミットする**（Laravel 公式推奨）。本番ビルドで再現性を担保するため。

## autoload 設定

PSR-4 で 4 つのレイヤーを宣言する:

```json
{
    "autoload": {
        "psr-4": {
            "App\\Domain\\":         "app/Domain/",
            "App\\UseCase\\":        "app/UseCase/",
            "App\\Interface\\":      "app/Interface/",
            "App\\Infrastructure\\": "app/Infrastructure/",
            "Database\\Factories\\": "database/factories/",
            "Database\\Seeders\\":   "database/seeders/"
        }
    },
    "autoload-dev": {
        "psr-4": {
            "Tests\\": "tests/"
        }
    }
}
```

- Laravel 標準の `App\\` 単一プレフィックスは使わず、レイヤーごとに分割する
- これによりレイヤー違反（`App\Domain` から `Illuminate\...` を使う等）を発見しやすくなる

## 依存ルール

### require / require-dev の分離

本番に必要な依存は `require`、開発ツール・テストは `require-dev` に置く。本番イメージは `composer install --no-dev --prefer-dist` でビルドする。

### 標準 dev セット

すべての PHP プロジェクトに以下を含める:

```json
{
    "require-dev": {
        "larastan/larastan": "^3.0",
        "laravel/pint":      "^1.0",
        "pestphp/pest":      "^3.0",
        "pestphp/pest-plugin-laravel": "^3.0",
        "rector/rector":     "^2.0"
    }
}
```

- **larastan**: PHPStan + Laravel 拡張。レベルは max を目標
- **Laravel Pint**: フォーマッタ。PSR-12 準拠
- **Pest**: テスティングフレームワーク（`conventions.md` で推奨）
- **Rector**: 自動リファクタリング・PHP バージョンアップ対応

### レイヤー別の依存ルール

依存方向を `composer.json` レベルで強制することは PHP では難しいため、**deptrac** で静的に検査することを推奨する:

| レイヤー | 依存できる相手 |
|---|---|
| `App\Domain` | 外部依存（`ramsey/uuid`, `nesbot/carbon` 等）のみ。Laravel / Eloquent に依存しない |
| `App\UseCase` | `App\Domain` + 外部依存 |
| `App\Interface\Http` | `App\Domain` + `App\UseCase` + Laravel HTTP |
| `App\Interface\Persistence` | `App\Domain` + `App\UseCase` + Eloquent |
| `App\Infrastructure` | `App\UseCase`（`JwtConfig` 等の型のため）+ 設定系ライブラリ |
| `App\Providers` 配下 | 全レイヤー（DI 構築のため） |

deptrac 設定例（`deptrac.yaml`）:

```yaml
deptrac:
  paths:
    - ./app
  layers:
    - name: Domain
      collectors:
        - { type: classLike, value: App\\Domain\\.* }
    - name: UseCase
      collectors:
        - { type: classLike, value: App\\UseCase\\.* }
    - name: Interface
      collectors:
        - { type: classLike, value: App\\Interface\\.* }
  ruleset:
    Domain: ~
    UseCase:
      - Domain
    Interface:
      - Domain
      - UseCase
```

## composer scripts

すべてのプロジェクトで以下のスクリプトを揃える:

```json
{
    "scripts": {
        "lint":     "pint",
        "lint:check": "pint --test",
        "analyse":  "phpstan analyse --memory-limit=2G",
        "test":     "pest",
        "test:coverage": "pest --coverage --min=80"
    }
}
```

- `composer lint` — 自動整形
- `composer lint:check` — CI 用、整形差分チェックのみ
- `composer analyse` — 静的解析（larastan, max レベル）
- `composer test` — テスト実行

## マイグレーション

Laravel artisan のマイグレーション機能を使う:

```bash
php artisan make:migration create_users_table
php artisan migrate
php artisan migrate:rollback
php artisan migrate:fresh --seed   # 開発時のみ
```

`database/migrations/{timestamp}_{action}_{table}_table.php` 形式の PHP クラスで `up()` / `down()` を実装する。

> 注: 生 SQL ベースのリバーシブルマイグレーション（`~/.claude/rules/sql/migrations.md` の sqlx-cli 経路）は **Rust プロジェクト用** であり、Laravel プロジェクトでは artisan を使う。両者は別ルートとして区別する。

## `composer.json` のサンプル骨子

```json
{
    "name": "vendor/project-name",
    "type": "project",
    "license": "proprietary",
    "require": {
        "php": "^8.4",
        "laravel/framework": "^12.0",
        "ramsey/uuid": "^4.0"
    },
    "require-dev": {
        "larastan/larastan": "^3.0",
        "laravel/pint": "^1.0",
        "pestphp/pest": "^3.0",
        "pestphp/pest-plugin-laravel": "^3.0",
        "rector/rector": "^2.0"
    },
    "autoload": {
        "psr-4": {
            "App\\Domain\\": "app/Domain/",
            "App\\UseCase\\": "app/UseCase/",
            "App\\Interface\\": "app/Interface/",
            "App\\Infrastructure\\": "app/Infrastructure/",
            "Database\\Factories\\": "database/factories/",
            "Database\\Seeders\\": "database/seeders/"
        }
    },
    "autoload-dev": {
        "psr-4": {
            "Tests\\": "tests/"
        }
    },
    "scripts": {
        "lint": "pint",
        "lint:check": "pint --test",
        "analyse": "phpstan analyse --memory-limit=2G",
        "test": "pest"
    },
    "config": {
        "sort-packages": true,
        "optimize-autoloader": true
    },
    "minimum-stability": "stable",
    "prefer-stable": true
}
```

## 依存追加のチェックリスト

新規パッケージ追加時:

1. 用途に応じて `require` / `require-dev` のどちらに入れるか判断
2. メジャー固定 + マイナー以上許容（`^X.Y`）でバージョン指定
3. `composer.lock` を更新してコミット
4. 依存方向のルールに違反していないか確認（例: `App\Domain` から Laravel パッケージを引かない）
5. ライセンスを確認（プロプライエタリプロジェクトなら GPL 系は避ける）
