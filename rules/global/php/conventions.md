---
paths:
  - "**/*.php"
---

# PHP コーディング規約

PHP 8.4 + Laravel 12 でのコーディング規約。`architecture.md` と併せて読むこと。Rust 規約と思想を揃えている。

## 基本

### PSR-12 と strict types

- すべての PHP ファイル冒頭に `declare(strict_types=1);` を必須とする
- フォーマットは PSR-12 準拠。Laravel Pint で自動整形（`composer.md` 参照）
- 名前空間は PSR-4。`App\Domain\\`, `App\UseCase\\`, `App\Interface\\`, `App\Infrastructure\\` の配下に配置

### 型宣言

- 引数・戻り値型を宣言する
- `mixed` は原則禁止。どうしても必要な場合のみ理由をコメント
- `?T`（nullable）は最終手段。NULL を許容するなら設計を見直し、別型・別フローにできないか検討
- 複数型のユニオン（`int|string`）は API 境界での後方互換用以外では使わない

```php
public function findUserById(UserId $id): ?User
{
    // ...
}
```

## 標準パターン優先

独自メソッドより PHP 標準・型システムで表現する。

- 値オブジェクトの構築は **静的ファクトリ** `fromString()` / `fromInt()` で実装する（Rust の `TryFrom<String>` 相当）
- `__construct` は `private` にして外部から構築できなくする
- 文字列化は `__toString()` を実装する（`Stringable` インターフェース）

## 値オブジェクトのパターン

`final readonly class` + `private __construct` + 静的ファクトリ で「外部から自由に構築できないこと」を保証する。

```php
declare(strict_types=1);

namespace App\Domain\User;

use App\Domain\Exception\InvalidFormatException;

final readonly class UserId
{
    private function __construct(
        public string $value,
    ) {}

    public static function generate(): self
    {
        return new self(\Ramsey\Uuid\Uuid::uuid4()->toString());
    }

    public static function fromString(string $value): self
    {
        if (! \Ramsey\Uuid\Uuid::isValid($value)) {
            throw new InvalidFormatException("UserId must be a valid UUID, got: {$value}");
        }
        return new self($value);
    }

    public function __toString(): string
    {
        return $this->value;
    }
}
```

エンティティも `final class` + readonly プロパティ + `private __construct` + 静的ファクトリで構築する。

## 文字列値オブジェクトの統一

文字列ベースの値オブジェクトは長さ・形式バリデーションを共通基底トレイトまたは抽象クラスで統一する（Rust の `define_string!` マクロ相当）:

```php
namespace App\Domain;

abstract readonly class StringValue
{
    protected function __construct(public string $value) {}

    /**
     * @return static
     */
    protected static function build(
        string $value,
        ?int $min = null,
        ?int $max = null,
    ): static {
        $length = mb_strlen($value);
        if ($min !== null && $length < $min) {
            throw new InvalidLengthRangeException(static::class . " must be at least {$min} chars");
        }
        if ($max !== null && $length > $max) {
            throw new InvalidLengthRangeException(static::class . " must be at most {$max} chars");
        }
        return new static($value);
    }

    public function __toString(): string
    {
        return $this->value;
    }
}

// 利用側
final readonly class UserName extends StringValue
{
    public static function fromString(string $value): self
    {
        return self::build($value, max: 25);
    }
}
```

## PHP 8.4 機能の活用

### Backed Enum

列挙は **backed enum** で書く。DB の CHECK 制約 / ENUM 型と同期させる:

```php
enum RecipeStatus: string
{
    case Draft     = 'draft';
    case Published = 'published';
    case Archived  = 'archived';

    public function isVisible(): bool
    {
        return $this === self::Published;
    }
}
```

### Property Hooks（PHP 8.4）

派生プロパティを property hook で表現する場合は、計算結果のキャッシュ / 副作用がないことを担保する:

```php
final class Order
{
    public int $totalAmount {
        get => array_sum(array_map(fn($i) => $i->price, $this->items));
    }
}
```

### Asymmetric Visibility（PHP 8.4）

外部から読み取り可、書き込み内部のみのプロパティは asymmetric visibility で表現:

```php
final class Counter
{
    public private(set) int $value = 0;

    public function increment(): void
    {
        $this->value++;
    }
}
```

readonly で済むケースでは readonly を優先する（変更が不要なら不変が最善）。

## 例外（エラー）

### レイヤーごとの専用 Exception

各レイヤーで自分専用の Exception を定義する。Rust の `Error` enum + `From` 変換に対応:

```
App\Domain\Exception\InvalidFormatException
App\Domain\Exception\InvalidLengthRangeException
App\UseCase\Exception\InvalidArgumentException
App\UseCase\Exception\UnauthorizedException
App\UseCase\Exception\NotFoundException
...
App\Interface\Http\Exception\HttpException  (必要に応じて)
```

### Catch & Rethrow で型変換

下位レイヤーの Exception を上位レイヤーの Exception に変換する:

```php
public function handle(RegisterUserRequest $req): RegisterUserResponse
{
    try {
        $email = Email::fromString($req->email);
        $name  = UserName::fromString($req->name);
    } catch (InvalidFormatException | InvalidLengthRangeException $e) {
        throw new InvalidArgumentException($e->getMessage(), previous: $e);
    }
    // ...
}
```

`previous` パラメータで元 Exception を保持する（スタックトレースが追える）。

## DI

### コンストラクタインジェクション only

UseCase 層では Service Locator（`app()->make()`）・Facade（`Auth::user()` 等）を使わない。すべてコンストラクタで受け取る。

```php
final class RegisterUserInteractor
{
    public function __construct(
        private readonly UserRepositoryInterface $userRepository,
        private readonly LoggerInterface $logger,
    ) {}
}
```

Controller でのファサード使用は許容する（Laravel 慣習との折衷）。ただし Interactor を呼んだら結果を返すだけなのでファサードを使う場面は少ない。

## Eloquent の使い方

### Repository 内に閉じ込める

Eloquent モデルは `app/Interface/Persistence/Eloquent/Models/` に置き、UseCase / Domain には渡さない。Repository 内で Eloquent ↔ ドメインモデル変換を行う:

```php
final class UserRepository implements UserRepositoryInterface
{
    public function findById(UserId $id): ?User
    {
        $row = UserModel::query()->find($id->value);
        return $row === null ? null : $this->toDomain($row);
    }

    public function save(User $user): void
    {
        UserModel::query()->updateOrCreate(
            ['id' => $user->id->value],
            [
                'email' => (string) $user->email,
                'name'  => (string) $user->name,
            ],
        );
    }

    private function toDomain(UserModel $row): User
    {
        return User::reconstruct(
            id:    UserId::fromString($row->id),
            email: Email::fromString($row->email),
            name:  UserName::fromString($row->name),
        );
    }
}
```

### `whereRaw` 原則禁止

`whereRaw` / `DB::raw()` は SQL インジェクションの温床。クエリビルダで表現できないケースのみ使い、必ずパラメータバインドを使う。

## テスト

- `tests/Unit/` — Interactor の単体テスト。Repository はモックまたはインメモリ実装で差し替え
- `tests/Feature/` — HTTP レイヤーから Interactor 経由で実 DB に書き込む統合テスト
- **Pest** を推奨（PHPUnit でも可）
- `RefreshDatabase` トレイトで実 PostgreSQL に接続する
- ファクトリ（`UserFactory` 等）は `database/factories/` に配置（Laravel 標準）

## 命名

| 対象 | 規則 | 例 |
|---|---|---|
| クラス | `UpperCamelCase` | `UserRepository` |
| メソッド | `camelCase` | `findById`, `saveUser` |
| 変数・プロパティ | `camelCase` | `$userRepository` |
| 定数 | `UPPER_SNAKE_CASE` | `MAX_RETRY_COUNT` |
| ファイル名 | クラス名と一致 | `UserRepository.php` |
| 値オブジェクト | `{Entity}{Attribute}` | `UserId`, `UserName`, `Email` |
| Interactor | `{Action}{Entity}Interactor` | `RegisterUserInteractor` |
| Interactor メソッド | `handle` | `$interactor->handle($request)` |
| Repository インターフェース | `{Entity}RepositoryInterface` | `UserRepositoryInterface` |
| Repository メソッド | `save*` / `findBy*` / `update*` / `delete*` | `findByEmail`, `saveUser` |
| Controller | `{Action}{Entity}Controller` | `RegisterUserController` |
| FormRequest | `{Action}{Entity}Request` | `RegisterUserRequest` |
| Resource | `{Entity}Resource` | `UserResource` |

## ロギング

Laravel の `Log` ファサードではなく、PSR-3 の `Psr\Log\LoggerInterface` をコンストラクタインジェクションで受け取る。フレームワーク非依存にできる:

```php
public function __construct(
    private readonly LoggerInterface $logger,
) {}
```
