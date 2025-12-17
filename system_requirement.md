Antigravity Cortex (Knowledge Core) 要件定義書
1. はじめに (Introduction)
1.1 システム名称
Antigravity Cortex (アンチグラビティ・コーテックス)
通称: Knowledge Core
1.2 目的 (Purpose)
ユーザーの「個人属性（Facts）」、「現在の状態（States）」、「過去の経験（Episodes）」を構造化して蓄積し、Antigravity OSを含むあらゆるAIエージェントに対し、「ユーザーに関する文脈（Context）」 をAPI経由で提供する。
これにより、AIがユーザーの暗黙知や状況を理解し、より精度の高い判断を行えるようにする。
本システムは「ユーザー単位の文脈提供」に加え、クライアント（アプリ／AIエージェント）単位のスコープ（共有範囲）制御を可能とする。
これにより、全エージェント共通で参照すべき記憶と、特定エージェント専用の記憶（例：Finance担当AI専用）を分離し、誤参照・コンテキスト汚染を防止する。

1.3 設計哲学 (Philosophy)
    1. Decoupling (完全な独立性):
メインのタスク管理アプリ（Antigravity OS）から切り離された独立したサービスとして設計する。これにより、将来的に他のツール（CLI、ブラウザ拡張、IoTデバイスなど）からも「ユーザーの文脈」を参照可能にする。
    2. Atomic Information (情報の原子性):
曖昧なチャットログをそのまま保存せず、AIによる解析を経て「最小単位の事実」に分解してから保存する。これにより、情報の再利用性と検索精度を高める。
    3. Active Memory (能動的な記憶):
単なるデータベースではなく、入力された情報に対して「これは既存の情報の更新か？ 新規か？」を自律的に判断するロジック（Memory Manager）を持つ。
    4. Scope Isolation（スコープ分離）:
    記憶は「ユーザー共通（Global）」と「特定クライアント／エージェント専用（Agent-scoped）」に分離して管理する。
    これにより、複数のAIエージェントが同一ユーザーの記憶を利用する際の、意図しない混線を防ぐ。
2. システムアーキテクチャ (System Architecture)
本システムは、HTTP通信を受け付けるAPIサーバーと、推論を行うAIエンジン、データを保持するデータベースで構成されるマイクロサービスである。
graph TD
    Client((Client App / OS))
    
    subgraph "Antigravity Cortex (Microservice)"
        API[API Gateway (FastAPI)]
        Logic[🧠 Memory Manager (AI Logic)]
        DB[(Knowledge DB)]
    end
    
    %% Input Flow
    Client -- "1. POST /ingest (Raw Text)" --> API
    API --> Logic
    Logic -- "Extract & Classify" --> Logic
    Logic -- "Upsert / Append" --> DB
    
    %% Output Flow
    Client -- "2. GET /memories (Label)" --> API
    Client -- "3. POST /context (RAG)" --> API
    API --> Logic
    Logic -- "Semantic Search" --> DB
    DB -- "Vector Data" --> Logic
    Logic -- "Synthesize Context" --> API
    API -- "Structured Context" --> Client

3. データ構造設計 (Data Structure)
    • 本システムは記憶を以下の2軸で管理する。
        ○ User Axis: どのユーザーに属する記憶か（user scope）
        ○ Client/Agent Axis: どのクライアント／AIエージェントのための記憶か（agent scope）
    • これにより、同一ユーザーの記憶であっても、用途（タスク管理、投資、学習支援等）に応じたスコープ分離を可能にする。
3.1 データベース・スキーマ (Supabase / PostgreSQL)
本システムは、PostgreSQL (Supabase) を採用し、ベクトル検索拡張 pgvector を利用する。
データモデルは、知識の実体を管理する memories テーブルと、変更履歴を追跡する memory_audit_logs テーブルの2つを核として構成する。Shutterstock
コード スニペット

erDiagram
    memories ||--o{ memory_audit_logs : "has history"
    
    memories {
        uuid id PK
        uuid user_id "Owner"
        text content "Knowledge Body"
        vector embedding "768 dim"
        enum memory_type "FACT/STATE/EPISODE"
        text[] tags
        enum scope "global/agent"
        text agent_id "Nullable"
        timestamp valid_from
        timestamp valid_to
        jsonb related_entities
    }
memory_audit_logs {
        uuid id PK
        uuid memory_id FK
        enum action "create/update/delete"
        jsonb diff "Changes"
        timestamp created_at
    }
3.1.1 Table: memories (知識リポジトリ)
すべての知識（Fact, State, Episode）を格納するメインテーブル。意味検索（Vector Search）とメタデータ検索の双方に対応する。
Column Name	Type	Constraints	Description
id	UUID	PK, default gen_random_uuid()	レコード固有ID
user_id	UUID	Not Null, Index	データの所有ユーザーID（RLS用）
content	Text	Not Null	知識の実体（例: "ユーザーは朝型の執筆を好む"）
embedding	Vector(768)	Index (HNSW/IVFFlat)	content のベクトル埋め込みデータ
memory_type	Enum	Not Null	fact, state, episode, policy （更新ロジックの分岐に使用）
tags	Text[]	Index (GIN)	AIが付与した分類タグ（例: ["preference", "research"]）
scope	Enum	Default 'global'	global: 全エージェント共有, agent: 特定エージェント専用
agent_id	Text	Nullable	scope=agent の場合の対象クライアントID（例: "finance-agent"）
importance	SmallInt	Default 3	1(低)〜5(高)。RAG取得時の優先度制御に使用
confidence	Real	Default 0.7	0.0〜1.0。抽出結果の確信度（低いものは要確認）
related_entities	JSONB	Nullable, Index (GIN)	関連エンティティ（例: ["project:LBS", "person:mentor_X"]）。回顧・検索用
source	Text		情報源の識別子（例: "chat_log_20251127", "manual_input"）
input_channel	Enum		入力経路（chat, manual, api, import）
content_hash	Text	Unique Constraint (w/ scope)	正規化されたcontentのハッシュ値。完全一致の重複登録抑止用
ライフサイクル・時間管理カラム
Column Name	Type	Description
event_time	Timestamp	出来事が発生した日時（主にEpisode用）。日記や回想録としての時系列ソートに使用。
valid_from	Timestamp	Default now()。情報の有効開始日時（State管理用）。
valid_to	Timestamp	Nullable。無効化された日時（NULL=現在有効）。論理削除やStateの遷移で使用。
last_accessed	Timestamp	最終参照日時。忘却ロジックおよびRAGランキングの参照頻度指標として利用。
supersedes_id	UUID	Nullable。情報の更新（上書き）時に、旧レコードのIDを保持してリンクさせる。
created_at	Timestamp	Default now()。レコード作成日時（システム的なログ）。
updated_at	Timestamp	Default now()。最終更新日時。

3.1.2 Table: memory_audit_logs (監査・履歴)
手動修正・削除のトレーサビリティ確保、および誤更新時の復旧（Undo）を目的とした監査ログ。
Column Name	Type	Description
id	UUID	PK, default gen_random_uuid()
memory_id	UUID	FK -> memories.id。操作対象の記憶ID
action	Enum	create, update, delete, restore, confirm, reject
actor_type	Enum	system (AI/Logic), user (Manual), admin
diff	JSONB	変更前後の差分（{ "before": {...}, "after": {...} }）
created_at	Timestamp	Default now()。操作実行日時

3.1.3 インデックスと制約 (Indexes & Constraints)
パフォーマンスと整合性を担保するためのデータベース設定。
    1. Vector Search Index (pgvector)
        ○ embedding 列に対し、HNSW (Hierarchical Navigable Small World) または IVFFlat インデックスを作成し、コサイン類似度検索を高速化する。
    2. Tag Search Index (GIN)
        ○ tags および related_entities 列に GIN インデックスを作成し、タグの包含検索 (@>) を高速化する。
    3. Scope & Context Index
        ○ (user_id, scope, agent_id) の複合インデックスを作成し、エージェントごとのコンテキスト分離（フィルタリング）を高速化する。
    4. Unique Constraint (Deduplication)
        ○ (user_id, scope, agent_id, content_hash) に対してユニーク制約を設定。
        ○ 同一スコープ内での完全一致データの二重登録をDBレベルで防止する。

3.2 Memory Types (記憶の分類)
AIがデータの更新戦略を決定するための分類定義。
    1. FACT (固定事実):
        ○ 定義: 変更頻度が低い、客観的な事実。
        ○ 例: 名前、所属、誕生日、PCのスペック、アレルギー情報。
        ○ 更新戦略: 原則として**「上書き (Overwrite)」**。常に最新の真実を一つだけ保持する。
    2. STATE (現在の状態):
        ○ 定義: 時間経過とともに変化する、主観的または一時的な状態。
        ○ 例: 「今は光工学の実験に熱中している」「腰が痛い」「LBS負荷が高い」。
        ○ 更新戦略: 「最新優先 (Latest Wins)」。古い状態は無効化（または履歴テーブルへ移動）し、現在の状態を維持する。
    3. EPISODE (経験ログ):
        ○ 定義: 過去に起きた出来事の記録。
        ○ 例: 「論文Xを読んだが、手法Yは理解できなかった」「学会でZ氏と会った」。
        ○ 更新戦略: 「追記 (Append Only)」。過去の事実は消さずに積み上げる。

4. 機能要件 (Functional Requirements)
4.1 Input Flow: 自律的な記憶の整理 (Ingestion)
外部システムから投げられた非構造化データ（チャットログ等）を、構造化された知識に変換するプロセス。
    1. Analysis (解析):
        ○ Importance 判定（保存可否・優先度）:
        AIは入力テキストからChunkを生成する前に、当該テキストが「記憶として保存すべき情報」を含むかを判定する。
        保存対象とする基準例：
            § FACT に該当する情報は原則保存
            § STATE（健康・疲労・負荷・学習停滞など）に関する情報は優先的に保存
            § 再利用性が低い雑談・感想のみの発話は **importance を低く設定（例:1）**するか、保存をスキップ可能とする
        ○ 含まれている場合、それを「主語 + 述語 + 目的語」のような原子的な短文（Chunk）に分割する。
        ○ Normalization（正規化）:
        Chunk生成後、Dedup/Upsert の安定性を高めるため、以下の正規化を実施する。
            § 表記ゆれの統一（例: "TOEIC" / "Toeic"）
            § 日付表現の統一（相対表現→絶対日付に変換可能なら変換）
            § 主語の補完（省略されている場合は "ユーザー" を補完）
        ○ 各Chunkに対し、Memory Type (Fact/State/Episode) と Tags を推定する。
    2. Deduplication (重複排除):
        ○ 生成されたChunkのembeddingでDBを検索し、類似レコードを確認する。
            § 対象フィルタ: user_id および scope（必要なら agent_id）で限定する
            § 判定は Memory Type により分岐する
                □ FACT / STATE:
Similarity が閾値以上（例:0.95）かつ同一カテゴリと判断される場合、**更新候補（Upsert判定）**へ進む（単純スキップしない）
                □ EPISODE:
原則として dedup しない（類似でも別出来事として Append）。ただし完全一致（content_hash一致）のみスキップ可能
    3. Upsert Strategy (更新判断):
        ○ 既存の関連情報と矛盾する場合、Memory Type に基づいて処理を決定する。
            § FACT / STATE の更新:
            古い情報を物理削除せず、以下を基本とする。
                • 旧レコード: valid_to を設定して無効化
                • 新レコード: Insert（valid_from=now, valid_to=NULL）
                • 新レコードの supersedes_id に旧レコードIDを格納
これにより、誤更新時の復旧（ロールバック）と履歴分析が可能となる。
            § EPISODE: 新しい情報を別レコードとしてInsertする。
4.2 Output Flow: コンテキスト提供 (Retrieval)
クライアントの要求に応じて、最適な形式で知識を提供するインターフェース。
Pattern 1: Direct Label Query
    • 概要: 指定されたタグを持つ全データを返す。
    • Input: tags=["茶道", "スケジュール"]
    • Process: 単純なSQLクエリ (SELECT * FROM memories WHERE tags @> ...)。
    • Use Case: 特定プロジェクトの全背景知識を一括ロードする場合。
Pattern 2: Raw Dump
    • 概要: データベースの全内容をバックアップ用にエクスポートする。
    • Input: なし（管理者権限必須）
    • Process: 全件取得し、JSONL形式でストリーム出力。
Pattern 3: AI-Synthesized Context (RAG)
    • 概要: クライアントの状況（Context）に合わせて、AIが必要な情報を検索・要約して返す。
    • Input:
        ○ query: ユーザーの現在の発言や悩み（例: "来週のタスク計画を立てたい"）
        ○ app_context: アプリ側の状態（例: "LBS負荷=High"）
    • Process:
        1. Vector Search: query と app_context のベクトルに近い記憶を検索。
        2. Re-ranking: 検索結果から app_context に関連性の高いものをフィルタリング。
        3. Cutoff: Re-rankingされた上位の記憶から順に、LLMのコンテキストウィンドウ（例: 入力上限の20%など）に収まる範囲で採用する情報を切り詰める。
        4. Synthesis: DB側のAIが検索結果を読み込み、回答生成に役立つ形に要約する。
            § 「ユーザーは現在疲労状態（State）であり、過去に過密スケジュールで失敗した経験（Episode）があります。」
    • Use Case: Antigravity OSのHubが、ユーザーへのアドバイスを生成する前段として呼び出す。
    • Ranking Policy
        • Recency Decay:
            • STATE / EPISODE は時間経過によりスコアを減衰
            • FACT / POLICY は原則減衰しない
        • Importance:
            • importance が高い記憶は常に優先
        • Confidence:
            • confidence が低い記憶はスコアを下げる
            • 必要に応じて「仮説」として明示的にラベル付け
        • State:
            • STATE（現在の状態）に関しては、スコア減衰だけでなく、valid_to が設定されている（過去の解決済み状態）ものや、更新から一定期間（例: 24時間）以上経過したものは、RAGのコンテキストに含めない、あるいは「過去の状態」として明示的に区別するロジックを組み込む。
    • Global/Agent scope prioritization
        • Retrieval は以下の優先順位で記憶を参照する：
            1. 同一 agent_id かつ scope="agent"
            2. scope="global"
        • agent 専用記憶が存在する場合、global 記憶より優先される
4.3 Management UI: 記憶の庭師 (Memory Gardener)
管理者（ユーザー）がデータベースの状態を直接メンテナンスするためのGUIツールを提供する。APIを経由せず、DBに直接（または内部API経由で）アクセスする。
    • Search & Inspect: 自然言語クエリまたはタグで記憶を検索し、AIが「何を覚えているか」を確認する機能。
    • Manual Override: 誤った記憶（Hallucination）の手動修正・削除機能。
    • Force Ingest: AIの解釈を挟まず、強制的に特定のFACT（例: APIキー、新しい住所）を登録する機能。
        ○ Force Ingest は、AIの解析・分割・dedup を経由せず、指定された memory_type と tags で登録できること。
        例: APIキー等の高リスク情報を確実に FACT として登録する用途。

5. APIインターフェース設計 (API Spec Draft)
FastAPIでの実装を想定したエンドポイント定義。
5.1 共通仕様（全API共通）
項目	内容
認証	X-API-KEY ヘッダ必須
バージョニング	URL パスで管理（/v1/...）
冪等性	POST /v1/ingest は Idempotency-Key ヘッダ対応（推奨）
レスポンス形式	JSON
エラー形式	統一エラーフォーマット（後述）

5.2 Ingestion 系 API
POST /v1/ingest — 非構造テキストの解析・記憶化
項目	内容
概要	非構造テキストを解析し、記憶（FACT / STATE / EPISODE 等）として保存
主用途	チャットログ、日記、外部サービス入力
後方互換	既存 payload はそのまま利用可
Request Body
フィールド	型	必須	説明
text	string	✔	入力テキスト
source	string	✔	入力元（chat / manual / api 等）
user_id	string		ユーザー識別子（将来拡張用）
agent_id	string		呼び出し元クライアント
scope	string		global / agent（default: global）
event_time	datetime		出来事発生時刻（主に EPISODE 用）
metadata	object		会話ID等の補助情報
Response（例）
フィールド	説明
ingest_id	Ingest 処理ID
created_count	新規作成数
updated_count	更新数
skipped_count	スキップ数
memory_ids	対象 memory_id 一覧
warnings	矛盾・低confidence等

POST /v1/memories — Force / Manual Ingest
項目	内容
概要	AI解析を通さず、指定内容を直接登録
主用途	FACT / POLICY / 設定系情報の確定登録
Request Body
フィールド	型	必須	説明
content	string	✔	記憶内容
memory_type	string	✔	FACT / STATE / EPISODE 等
tags	array		タグ
user_id	string		ユーザー識別子
agent_id	string		クライアント識別子
scope	string		global / agent
importance	int		優先度（1–5）

5.3 Retrieval 系 API
GET /v1/memories — 記憶の検索・取得
項目	内容
概要	条件指定による記憶検索
主用途	UI表示、分析、デバッグ
Query Parameters
パラメータ	説明
user_id	ユーザー指定
scope	global / agent
agent_id	agent scope 指定時に使用
memory_type	FACT / STATE / EPISODE
tags	カンマ区切り
q	簡易全文検索
valid_at	指定時点で有効な記憶
from / to	時間範囲
limit	件数（default 50）
cursor	ページング用

POST /v1/context — 文脈合成（RAG）
項目	内容
概要	Knowledge Core が自律的に関連記憶を検索・要約
主用途	AI エージェントへの文脈供給
profile	使用しない（自動最適化）
Request Body
フィールド	型	必須	説明
query	string	✔	現在の問い・発話
app_context	object		呼び出し側の状態
user_id	string		ユーザー識別子
agent_id	string		呼び出し元
scope	string		global / agent
k	int		検索候補数
include_global	bool		agent scope 時に global を含める
return_evidence	bool		根拠を返すか
Response（例）
フィールド	説明
context.summary	要約文
context.bullets	箇条書き
evidence	使用 memory_id とスコア

5.4 管理・メンテナンス系 API
PATCH /v1/memories/{id} — 記憶の手動修正
項目	内容
概要	content / tags / importance 等の修正
主用途	Memory Gardener

DELETE /v1/memories/{id} — 記憶削除
項目	内容
概要	指定記憶の削除（論理／物理は実装依存）

GET /v1/dump — データエクスポート（管理者）
項目	内容
概要	記憶データの一括取得
権限	管理者のみ
Query Parameters
パラメータ	説明
user_id	対象ユーザー
scope	global / agent
agent_id	agent 指定
format	json / jsonl

5.5 共通エラーフォーマット
{
  "error": {
    "code": "INVALID_ARGUMENT",
    "message": "agent_id is required when scope=agent",
    "details": {
      "field": "agent_id"
    }
  }
}

6. 技術スタック (Tech Stack)
独立性とコストパフォーマンスを重視した構成。
    • Runtime: Python 3.10+ (FastAPI)
    • Database: PostgreSQL + pgvector
        ○ メインアプリとは別プロジェクト、または別スキーマ (cortex) での管理を推奨。
    • AI Model (Hybrid):
        ○ Reasoning/Synthesis: Gemini 2.5 flash light (文脈理解、高度な要約用)
        ○ Extraction/Tagging: Gemini 2.5 flash light or Local LLM (Ollama/Gemma) (高速・低コストな分類用)
        ○ Embedding: text-embedding-004 (Gemini) or OpenAI text-embedding-3-small
    • Ingest処理の非同期 (Async)
        ○ APIはリクエストを受け付けたら即座に 202 Accepted と job_id を返す。
        ○ 裏側（Background Task / Celeryなど）でAI処理を行う。
        ○ クライアントは別途 GET /v1/ingest/{job_id} で完了を確認する、あるいはWebhookを受け取る。
7. セキュリティ要件
    • API Key Management:
        ○ Cortexへのアクセスには X-API-KEY ヘッダーを必須とする。キーはCortex側の環境変数で管理する。
    • Data Privacy:
        ○ 個人情報を含むため、DBへのアクセス権（RLS）は厳格に設定し、パブリックアクセスは一切許可しない。
