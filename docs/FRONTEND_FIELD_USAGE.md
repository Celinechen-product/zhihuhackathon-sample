# Frontend Field Usage

> Source: `not-working-new-zealand-demo.html`  
> Scope: only fields actually read by current frontend code.  
> Note: the page has local mock fallback from `mockPaths`, `mockPeople`, and `mockZhihuUser`.

## API Endpoints Read By The Frontend

| Endpoint | Method | When Used | Notes |
|---|---:|---|---|
| `/auth/me` | GET | Page boot session check | Replaces previous `/api/me`. Missing/401 redirects to Zhihu login; other errors use `mockZhihuUser` if mock fallback is enabled. |
| `/api/search?query=...&count=20` | GET | Default search after user submits home query | Current default path. If response has only `items[]`, frontend maps items into temporary people and uses mock paths. |
| `/api/demo/search` | POST | Only when `window.LIFE_PATH_USE_DEMO_SEARCH === true` | Future richer contract. Body is `{ query }`. |
| `/api/personas/chat` | POST | AI persona chat send | Optional. On failure or missing reply, frontend falls back to local persona reply. |
| `/api/samples/save` | POST | Save person to library | Fire-and-forget. Response is not read. |

## Session / Topbar

Interface source: `GET /auth/me`.

| Component | Actual Field Read | Required By Code | Missing Behavior |
|---|---|---:|---|
| Session check | `success` through `payload.data` / `payload.result` / root body | No | `normalizeZhihuUser` also checks `loggedIn`, `authenticated`, `isLoggedIn`, or presence of user id/name/avatar. |
| Session check | `data.user` / `data.profile` / `data.me` / `data` | No | Falls back to root body. |
| Topbar avatar | `id` / `userId` / `uid` | No | Falls back to `mockZhihuUser.id`. |
| Topbar avatar | `name` / `username` / `displayName` / `nickname` | No | Falls back to `mockZhihuUser.name`. |
| Topbar avatar | `avatar` / `avatarUrl` / `avatar_url` | No | Falls back to `mockZhihuUser.avatar`. |
| Topbar profile link | `profileUrl` / `profile_url` / `url` / `homepage` | No | Falls back to `mockZhihuUser.profileUrl`. |

Mock source: `mockZhihuUser`.

## Search Response Normalization

Interface source: default `GET /api/search`; optional `POST /api/demo/search`.

The frontend first resolves the response body from:

```text
payload.data.result || payload.data || payload.result || payload
```

### Top-Level Fields

| Actual Field Read | Required By Code | Missing Behavior |
|---|---:|---|
| `queryId` / `query_id` / `id` | No | `state.queryId` becomes empty/null; save/chat still work locally but backend association is weak. |
| `query` / `question` | No | Falls back to submitted query. |
| `analysis.steps` / `steps` / `analysisSteps` / `analysis_steps` | No | Falls back to `defaultAnalysisSteps(query)`. |
| `analysis.focusTags` / `analysis.focus_tags` / `focusTags` / `focus_tags` / `tags` | No | Falls back to default focus tags in `applySearchData`. |
| `paths` / `routes` / `directions` / `pathways` | Conditionally | If missing but `items[]` exists, frontend uses `mockPaths`. If both paths and people/items are missing, uses full mock payload. |
| `people` / `samples` / `personas` / `authors` | Conditionally | If missing but `items[]` exists, frontend maps `items[]` into people. If missing with no items, uses full mock payload. |
| `items` | Conditionally | Used only as fallback source for people when richer `people[]` is absent. |

Mock source: `mockPaths`, `mockPeople`, `defaultAnalysisSteps`.

## Path Cards / Paths Overview

Interface source: `paths[]` from `/api/demo/search`, or mock paths, or paths inferred from people.

| Component | Actual Field Read | Required By Code | Missing Behavior |
|---|---|---:|---|
| Path card action | `paths[].id` / `pathId` / `path_id` / `routeId` / `route_id` / `slug` | No | Generated from path name, e.g. `path_1`. Needed for meaningful `people[].pathId` matching. |
| Path card title | `paths[].name` / `title` / `label` / `pathName` | No | Falls back to `路径 N`. |
| Path card count | `count` / `peopleCount` / `people_count` / `sampleCount` / `sample_count` / `total` / `numPeople` | No | Shows `0 人走过`. |
| Path card desc | `desc` / `description` / `summary` / `reason` / `explanation` / `short` | No | Description area renders empty. |
| Path card short text | `short` / `subtitle` / `tagline` / `summary` / `description` | No | Stored but not visibly used in current path card. |
| Path card avatars | Matching `people[].avatar` by `people[].pathId === path.id` | No | Falls back to all people, then avatar fallback. Max 4 avatars shown. |

## Expanded Path Sample Stage

Interface source: normalized `people[]`.

| Component | Actual Field Read | Required By Code | Missing Behavior |
|---|---|---:|---|
| Moving avatar button | `people[].id` | No | Generated from name/index. Used as selection key. |
| Moving avatar image | `people[].avatar` / `avatarUrl` / `avatar_url` / `image` / `imageUrl` | No | Falls back to local OpenPeeps asset. |
| Moving caption | `people[].name` | No | Falls back to `样本 N`. |
| Moving caption | `people[].badge` / `tagline` / `keyExperience` / `key_experience` / `subtitle` / `oneLine` / `summary` | No | Caption second line empty. |
| Path grouping | `people[].pathId` / `path_id` / `routeId` / `route_id` / `path.id` / matched `pathName` | No | Falls back to first path. If wrong/missing, person appears under wrong path. |

## Person Card

Interface source: normalized `people[]`.

| Component | Actual Field Read | Required By Code | Missing Behavior |
|---|---|---:|---|
| Name link | `people[].name` | No | Falls back to `样本 N`. |
| Name link URL | `raw.profileUrl` / `profile_url` / `zhihuUrl` / `zhihu_url` / `homepage` / `url` | No | Falls back to `https://www.zhihu.com/people/{id-or-name}`. |
| Card avatar | `people[].avatar` | No | Falls back to local OpenPeeps asset. |
| `TA 是谁` | `who` / `bio` / `intro` / `profile` / `description` / `authorSummary` | No | Section renders empty paragraph. |
| `为什么匹配到 TA` | `overlaps` / `matchReasons` / `match_reasons` / `similarities` / `reasons` | No | Section renders empty list. |
| Timeline | `timeline` / `events` | No | Section renders empty timeline. Items may be arrays `[date,event]` or objects with `date/time/year/at` + `event/text/description/title`. |
| Article list | `articles` / `posts` / `contents` / `sources` | No | If absent but `articleBody/content/text` exists, one article is generated. If still absent, article list empty. |
| Article title | `articles[].title` / `name` | No | Falls back to `原文 N`. |

Mock source: `mockPeople`.

## Real Experience Reader

Interface source: `people[].articles[]`.

| Component | Actual Field Read | Required By Code | Missing Behavior |
|---|---|---:|---|
| Reader title | `articles[].title` | No | Falls back to generated title. |
| Reader meta | `articles[].author` / `authorName` / `author_name` | No | Falls back to person name or hidden from meta. |
| Reader meta | `articles[].sourceName` / `source` / `contentType` / `type` | No | Falls back to `知乎回答 / 文章`. |
| Reader meta | `articles[].publishedAt` / `published_at` / `createdAt` / `created_at` | No | Omitted from meta. |
| Original URL | `articles[].sourceUrl` / `source_url` / `url` / `link` | No | `查看知乎原文` link is hidden. |
| Reader body | `articles[].body` / `paragraphs` / `content` / `text` | No | Falls back to `person.articleBody`; otherwise body is empty. |
| Article id for chat | `articles[].id` / `articleId` / `article_id` | No | Generated as `article_N`; sent as `articleId` to chat. |

## Ask Modal / AI Persona Entry

No backend data is fetched when opening the modal. It uses current normalized person and local state.

| Component | Actual Field Read | Required By Code | Missing Behavior |
|---|---|---:|---|
| Modal aria label | `person.name` | No | Uses fallback person name. |
| Default question text | `person.badge` | No | Falls back to current path name. |
| Default question text | `person.pathId` | No | Used to find current path name. If missing, first path fallback. |
| Editable question | `state.questionText` | No | Defaults to local generated text. |

## AI Persona Chat Page

Interface source: normalized `people[]`, then `POST /api/personas/chat`.

### Chat Page Display Fields

| Component | Actual Field Read | Required By Code | Missing Behavior |
|---|---|---:|---|
| Sidebar avatar | `person.avatar` | No | Falls back to local OpenPeeps asset. |
| Sidebar name/title | `person.name` | No | Uses fallback name. |
| Sidebar role | `person.role` | No | Falls back to `知乎用户`. |
| Sidebar path | `person.pathId` | No | Falls back to first path name. |
| Disclaimer | `person.name` | No | Uses fallback name. |
| Persona reply fallback | `person.lesson` / `takeaway` / `keyLesson` / `key_lesson` / `conclusion` | No | Falls back to `person.oneLine`, then default text. |

### Chat Request Body

Sent to `POST /api/personas/chat`.

| Request Field | Source | Required By Code |
|---|---|---:|
| `queryId` | `state.queryId` from search response | No |
| `query` | `state.question` | Yes |
| `personId` | `person.id` | Yes |
| `articleId` | selected `articles[].id`, or `null` | No |
| `messages[].role` | local chat state, `ai` converted to `assistant` | Yes |
| `messages[].content` | local chat text | Yes |

### Chat Response Fields

The frontend reads the first available value:

```text
payload.data.result || payload.data || payload.result || payload
```

Then:

```text
reply || content || message || messages.at(-1).content
```

| Response Field | Required By Code | Missing Behavior |
|---|---:|---|
| `reply` / `content` / `message` / `messages[-1].content` | No | Falls back to local persona reply. Request failure also falls back locally. |

## My Library

The library is currently local-only.

| Component | Actual Field Read | Required By Code | Missing Behavior |
|---|---|---:|---|
| Question groups | `state.savedQuestionGroups[]` | No | Empty state shown. |
| Question title | `group.question` | Yes for rendered groups | Group is not created until user saves after a submitted search. |
| Saved count | `group.samples.length` | No | Count reflects rendered sample records. |
| Saved person id | `group.samples[].personId` | Yes for a saved row | Missing/unknown ids are filtered out. |
| Saved sample name | `person.name` | No | Uses fallback name. |
| Saved card avatar | `person.avatar` | No | Falls back to local OpenPeeps asset. |
| Saved card path | `person.pathId` | No | Falls back to first path. |
| Saved card text | `person.oneLine` | No | Empty paragraph if absent. |

Save action sends `POST /api/samples/save` with:

```json
{
  "queryId": "state.queryId",
  "query": "state.submittedQuestion || state.question",
  "personId": "selected person id"
}
```

The response is not read. Failure is ignored.

## Current Mock Fallback Rules

| Situation | Current Behavior |
|---|---|
| `GET /auth/me` returns 401/403 | Redirects to Zhihu OAuth login. |
| `GET /auth/me` fails for non-auth reasons | Uses `mockZhihuUser` when mock fallback is enabled. |
| Search request fails | Uses `mockSearchPayload(query)`, which returns `mockPaths` and `mockPeople`. |
| Search response lacks both `paths/people` and `items` | Uses `mockPaths` and `mockPeople`. |
| Search response has only `items[]` | Uses `mockPaths`; maps each item into a temporary `people[]` record. |

## Minimum Backend Shape For Full Non-Mock Demo

This is the smallest shape that avoids relying on `mockPaths` / `mockPeople`:

```json
{
  "success": true,
  "data": {
    "queryId": "query_123",
    "query": "用户问题",
    "analysis": {
      "steps": [
        { "title": "读取问题", "text": "..." }
      ],
      "focusTags": []
    },
    "paths": [
      {
        "id": "return",
        "name": "去了又回来",
        "count": 61,
        "desc": "..."
      }
    ],
    "people": [
      {
        "id": "person_001",
        "name": "知乎昵称",
        "pathId": "return",
        "role": "知乎用户",
        "badge": "关键经历",
        "avatar": "https://...",
        "profileUrl": "https://www.zhihu.com/people/...",
        "oneLine": "一句话摘要",
        "who": "TA 是谁",
        "overlaps": ["匹配理由"],
        "timeline": [
          { "date": "2024", "event": "经历节点" }
        ],
        "articles": [
          {
            "id": "article_001",
            "title": "知乎原文标题",
            "sourceUrl": "https://www.zhihu.com/...",
            "summary": "摘要",
            "body": ["可选正文"]
          }
        ]
      }
    ]
  }
}
```
