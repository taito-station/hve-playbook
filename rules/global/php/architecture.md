---
paths:
  - "**/*.php"
---

# PHP / Laravel クリーンアーキテクチャ規約

PHP 8.4 + Laravel 12 でバックエンド API を構築するときの規約。`~/.claude/rules/rust/architecture.md` の Rust 版規約と思想を揃え、Laravel 標準のレイヤーに **クリーンアーキテクチャ** を移植する。

## レイヤー構造と依存方向

依存方向は **App → Interface → UseCase → Domain**。逆方向の依存を作らない。

```
app/
├── Domain/                       # コアエンティティと値オブジェクト（Eloquent 非依存）
│   └── {Entity}/                 # 例: User/, Recipe/
├── UseCase/                      # ビジネスロジック
│   ├── {Entity}/{Action}/        # Interactor + Request/Response DTO
│   └── Repository/               # Repository インターフェース
├── Interface/
│   ├── Http/
│   │   ├── Controllers/          # HTTP ハンドラ（Interactor を呼ぶだけ）
│   │   ├── Requests/             # FormRequest による入力検証
│   │   └── Resources/            # JsonResource によるレスポンス整形
│   └── Persistence/
│       └── Eloquent/             # Repository インターフェースの Eloquent 実装
└── Infrastructure/
    └── Config/                   # 環境変数ベースの設定
```

`app/Models/` の Laravel 標準位置は使わない。Eloquent モデルは `app/Interface/Persistence/Eloquent/Models/` に集約する。

## 各レイヤーの責務

### Domain (`app/Domain/`)
- エンティティと値オブジェクトのみ。**外部依存なし**（Carbon 等の最小限のみ）
- Eloquent / Laravel の Facade を **絶対に import しない**
- バリデーションは値オブジェクトの static factory（`fromString()` 等）に集約
- ドメインエラーは `App\Domain\Exception\InvalidFormatException` / `InvalidLengthRangeException` のみに留める

### UseCase (`app/UseCase/`)
- フレームワーク非依存。Laravel の Facade / Container を持ち込まない
- `App\UseCase\Repository\{Entity}RepositoryInterface` を定義（実装は Persistence 層）
- `App\UseCase\{Entity}\{Action}\{Action}{Entity}Interactor` クラスにビジネスロジックを実装
- DTO は同パッケージに `{Action}{Entity}Request` / `{Action}{Entity}Response` として配置
- Exception は HTTP ステータスに対応する型を定義（後述のエラーマッピング表）

### Interface (`app/Interface/`)

#### Http (`app/Interface/Http/`)
- **Controllers**: 1 アクション 1 メソッド。FormRequest 検証 → Interactor 呼び出し → Resource 返却のみ
- **Requests**: `FormRequest` による入力検証。バリデーションルールはここに集約
- **Resources**: `JsonResource` によるレスポンス整形。ドメインモデルを受け取り JSON 構造に整える

#### Persistence (`app/Interface/Persistence/Eloquent/`)
- `Models/{Entity}Model.php`: Eloquent モデル（このレイヤーに閉じ込める）
- `{Entity}Repository.php`: `{Entity}RepositoryInterface` の実装。Eloquent → ドメインモデルへの変換を行う
- ドメインモデルを Eloquent モデルに、または逆に変換するロジックはこの層のみが知っている

### Infrastructure (`app/Infrastructure/Config/`)
- `.env` から読み込んだ設定値を型付きクラスにマッピング
- `JwtConfig`, `AuthConfig` のような設定オブジェクトを提供する

### App (Laravel bootstrap)
- `app/Providers/AppServiceProvider.php`: Repository インターフェース → Eloquent 実装の DI バインド
- `routes/api.php`: ルート定義
- `bootstrap/app.php`: Laravel 12 の bootstrap ファイル

## DI バインド

`AppServiceProvider::register()` で Repository インターフェースに実装をバインドする:

```php
public function register(): void
{
    $this->app->bind(
        \App\UseCase\Repository\UserRepositoryInterface::class,
        \App\Interface\Persistence\Eloquent\UserRepository::class,
    );
}
```

Interactor は コンストラクタインジェクションで RepositoryInterface を受け取り、Laravel の Container が解決する。

## Controller の責務

Controller は薄く保つ。**ビジネスロジックを書かない**:

```php
final class RegisterUserController
{
    public function __construct(
        private readonly RegisterUserInteractor $interactor,
    ) {}

    public function __invoke(RegisterUserRequest $request): UserResource
    {
        $response = $this->interactor->handle(
            new RegisterUserUseCaseRequest(
                email: $request->validated('email'),
                name: $request->validated('name'),
                password: $request->validated('password'),
            ),
        );

        return new UserResource($response->user);
    }
}
```

シングルアクションコントローラ（`__invoke`）を基本とする。

## エラーマッピング

UseCase 層の Exception を HTTP ステータスにマッピングする。Rust 規約のエラーマッピングと完全に対応させる:

```
App\UseCase\Exception\*           → HTTP Status
─────────────────────────────────────────────────
InvalidArgumentException          → 400
UnauthorizedException             → 401
ForbiddenException                → 403
NotFoundException                 → 404
AlreadyExistException             → 409
PreconditionFailedException       → 412
ExternalServerException           → 500
```

集約変換は `bootstrap/app.php` の `withExceptions()` で行う（Laravel 11+ の方式）:

```php
->withExceptions(function (Exceptions $exceptions): void {
    $exceptions->render(function (InvalidArgumentException $e, Request $request) {
        return response()->json(['message' => $e->getMessage()], 400);
    });
    // ... 他の Exception も同様
})
```

各レイヤーが独自の Exception を持ち、上位レイヤーで catch して上位の Exception に rethrow する（`Domain\Exception\InvalidFormatException` を catch して `UseCase\Exception\InvalidArgumentException` を投げる等）。

## 新リソース追加時のファイル作成手順

`{Entity}` を新しいエンティティ名（`User`, `Recipe` 等）に置換して以下を作成。

1. **Domain Entity**: `app/Domain/{Entity}/{Entity}.php` — エンティティ本体
2. **Domain Value Objects**: `app/Domain/{Entity}/{Entity}Id.php`, `{Entity}Name.php` 等
3. **UseCase DTO**: `app/UseCase/{Entity}/{Action}/{Action}{Entity}Request.php` / `{Action}{Entity}Response.php`
4. **UseCase Interactor**: `app/UseCase/{Entity}/{Action}/{Action}{Entity}Interactor.php`
5. **Repository Interface**: `app/UseCase/Repository/{Entity}RepositoryInterface.php` — メソッド命名は `save*` / `findBy*` / `update*` / `delete*` で Rust 規約と統一
6. **Eloquent Model**: `app/Interface/Persistence/Eloquent/Models/{Entity}Model.php`
7. **Eloquent Repository**: `app/Interface/Persistence/Eloquent/{Entity}Repository.php` — RepositoryInterface の実装
8. **HTTP Resource**: `app/Interface/Http/Resources/{Entity}Resource.php`
9. **HTTP Form Request**: `app/Interface/Http/Requests/{Action}{Entity}Request.php`
10. **HTTP Controller**: `app/Interface/Http/Controllers/{Action}{Entity}Controller.php`
11. **Route**: `routes/api.php` に `Route::post(...)` 等を追加
12. **Migration**: `database/migrations/{timestamp}_create_{entities}_table.php` — Laravel artisan 形式（`composer.md` 参照）
13. **DI バインド**: `AppServiceProvider::register()` に Repository バインドを追加

## 認証

JWT 認証が必要な場合は以下のパターンを踏襲（Rust の `fridgers-backend` パターンを PHP に移植）:

- パスワードは `password_hash($pwd, PASSWORD_ARGON2ID)` でハッシュ化
- JWT は `firebase/php-jwt` または `lcobucci/jwt` で発行
- `App\Infrastructure\Config\JwtConfig` クラスに `$secret` `$expiryHours` を保持
- 環境変数: `AUTH_JWT_SECRET` / `AUTH_JWT_EXPIRY_HOURS`
- 認証ミドルウェアは `app/Interface/Http/Middleware/JwtAuthMiddleware.php` に配置
