import React from "react";

export default class RouteErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("Route render failed", error, info);
  }

  componentDidUpdate(prevProps) {
    if (prevProps.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div className="rounded-lg border border-red-900/60 bg-red-950/30 p-5">
        <div className="text-sm font-semibold text-red-100">This view hit a problem.</div>
        <p className="mt-2 text-xs leading-relaxed text-red-200/80">
          The live shell is still running. Refresh this view or switch tabs while we recover the data.
        </p>
        <button
          type="button"
          onClick={() => this.setState({ error: null })}
          className="mt-4 rounded bg-red-800 px-3 py-1.5 text-xs font-semibold text-red-50 hover:bg-red-700"
        >
          Try again
        </button>
      </div>
    );
  }
}
