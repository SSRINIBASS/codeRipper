# Frontend SRS - Repo Intelligence Platform

## 1. Introduction
This document outlines the Software Requirements Specification (SRS) for the frontend web application of the Repo Intelligence Platform. The application will serve as the user interface for developers to ingest, analyze, search, and chat with their software repositories.

## 2. Technology Stack & Design System

### 2.1 Core Stack
- **Framework**: Next.js 14+ (App Router) for server-side rendering and routing.
- **Styling**: Tailwind CSS for utility-first styling.
- **State Management**: React Query (TanStack Query) for server state/caching, Zustand for local client state.
- **Icons**: Lucide React.
- **Markdown Rendering**: `react-markdown` with `syntax-highlighter` for code blocks.

### 2.2 Design Aesthetic: Neobrutalism
The interface will follow a **Neobrutalism** art style to achieve a "funky yet modular" look. Key characteristics:
- **High Contrast**: Bold black borders (`border-2` or `border-4`) on cards, buttons, and inputs.
- **Sharp Shadows**: Hard, offset shadows (e.g., `box-shadow: 4px 4px 0px 0px #000`) instead of soft blurs.
- **Vibrant Palette**: Use of saturated primary colors (Neo-Green, Hot Pink, Electric Blue, Vivid Yellow) against stark white/black backgrounds to define modules.
- **Typography**: Bold, geometric headings (e.g., `Clash Display` or `Space Grotesk`) paired with highly readable sans-serif or monospace body text.
- **Modular Layout**: Content organized in distinct, grid-aligned "blocks" or "bento box" style layouts with thick dividers.
- **Interactive Elements**: Buttons should have distinct "pressed" states (shadow disappears) to mimic physical tactility.

## 3. User Flows

### 3.1 Repository Ingestion
1. User lands on **Dashboard**.
2. User clicks "Add Repository".
3. User enters GitHub URL (e.g., `https://github.com/owner/repo`).
4. System validates URL and initiates ingestion via API.
5. Repository appears in list with "Cloning..." status.
6. Progress bars update in real-time (polling).

### 3.2 Intelligence & Support
1. User navigates to **Repo Details**.
2. If status is `STRUCTURED` but not `INDEXED`, user clicks "Start Indexing".
3. Once `INDEXED`, user can:
   - **Search**: Semantic search across the codebase.
   - **Generate Docs**: Auto-generate README/Architecture.
   - **Tutor**: Ask questions in the "Tutor" tab.

## 4. Feature Requirements

### 4.1 Dashboard (`/`)
- **Repository Grid**: Display cards for each ingested repository.
  - **Info**: Owner/Name, Primary Language, Size, Status Badge.
  - **Status Badges**: Color-coded (e.g., Green for READY, Yellow for INDEXING, Red for FAILED).
  - **Actions**: "View Details", "Delete".
- **Add Repo Modal**:
  - Input: GitHub URL.
  - Option: "Force Re-ingest" checkbox.
  - Submit Button.

### 4.2 Repository Details (`/repos/[id]`)
A layout with a side or top navigation bar containing the following tabs:

#### A. Overview Tab
- **Stats Card**: Total Files, Total Size, Commit Hash.
- **Language Breakdown**: Simple chart or list.
- **Status Pipeline Visualization**: Stepper showing [Ingest -> Index -> Docs].
- **Actions**:
  - "Index Repository" (if not indexed).
  - "Generate Documentation" (if indexed but no docs).

#### B. Code Browser Tab (`/repos/[id]/code`)
- **File Explorer**: Tree view of the repository structure (API: `/repos/{id}/structure`).
- **Code Viewer**: Read-only editor view with syntax highlighting.
- **Breadcrumbs navigation**.

#### C. Semantic Search Tab (`/repos/[id]/search`)
- **Search Input**: Large search bar.
- **Results List**: List of code chunks with:
  - File path/line numbers.
  - Relevance score.
  - Code snippet preview.
- **Filters**: Min score, file pattern.

#### D. Documentation Tab (`/repos/[id]/docs`)
- **Sub-tabs**: "README", "Architecture".
- **Markdown Viewer**: Render the generated markdown content.
- **Regenerate Button**: Option to re-run the LLM documentation job.

#### E. Tutor (Q&A) Tab (`/repos/[id]/tutor`)
- **Session Management**: "New Chat" button to start fresh context.
- **Chat Interface**:
  - User ID / Avatar.
  - AI Message with "Thinking" state.
  - **Citations**: Functionality to show "References" (File paths + line ranges) used by the AI to answer. Clicking a reference should open the Code Viewer at that location.
  - **Input Area**: Multiline text input.

## 5. API Mapping
The frontend will interface with the existing FastAPI backend (`http://localhost:8000`):

| Feature | API Endpoint | Method |
| :--- | :--- | :--- |
| **List Repos** | `/repos` | `GET` |
| **Add Repo** | `/repos/ingest` | `POST` |
| **Get Repo** | `/repos/{id}` | `GET` |
| **Delete Repo** | `/repos/{id}` | `DELETE` |
| **Repo Status** | `/repos/{id}/status` | `GET` |
| **File Tree** | `/repos/{id}/structure` | `GET` |
| **Start Index** | `/intelligence/{id}/index` | `POST` |
| **Search** | `/intelligence/{id}/search` | `GET` |
| **Start Docs** | `/intelligence/{id}/docs` | `POST` |
| **Get README** | `/intelligence/{id}/docs/readme` | `GET` |
| **Get Arch** | `/intelligence/{id}/docs/architecture` | `GET` |
| **Create Session** | `/tutor/{id}/session` | `POST` |
| **Ask Question** | `/tutor/{id}/ask` | `POST` |

## 6. Non-Functional Requirements
- **Polling**: Frontend must poll job status endpoints (`/repos/{id}/status`) every 3-5 seconds when a job is running to provide live feedback.
- **Responsiveness**: Must work on Desktop and Tablet sizes.
- **Error Handling**: Graceful toast notifications for API failures (e.g., "Repo not found", "Rate limit exceeded").

## 7. Future Considerations
- **Authentication**: Login screen for multi-user support.
- **Dark Mode**: Toggle support.
