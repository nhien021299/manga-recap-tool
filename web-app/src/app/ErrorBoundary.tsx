import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends Component<{ children: ReactNode }, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("APP RENDER ERROR:", error, errorInfo);
  }

  private resetLocalWorkspace = () => {
    localStorage.removeItem("manga-recap-storage-v11");
    window.location.reload();
  };

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-6 text-foreground">
        <div className="w-full max-w-xl rounded-2xl border border-red-500/30 bg-red-500/10 p-6 shadow-2xl">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-red-200">Frontend runtime error</p>
          <h1 className="mt-3 text-2xl font-bold text-white">App could not render this workspace state</h1>
          <pre className="mt-4 max-h-64 overflow-auto whitespace-pre-wrap rounded-xl border border-white/10 bg-black/30 p-4 text-xs text-red-50/90">
            {this.state.error.stack || this.state.error.message}
          </pre>
          <button
            type="button"
            onClick={this.resetLocalWorkspace}
            className="mt-5 rounded-xl border border-red-300/30 bg-red-300/15 px-4 py-2 text-sm font-semibold text-red-50 hover:bg-red-300/20"
          >
            Reset local workspace cache
          </button>
        </div>
      </div>
    );
  }
}
