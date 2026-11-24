import React, { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertCircle, RotateCw } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
  onReset?: () => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('[ErrorBoundary caught exception]:', error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 max-w-xl mx-auto flex flex-col items-center justify-center min-h-[400px] text-center">
          <div className="w-16 h-16 rounded-2xl bg-rose-50 border border-rose-200 flex items-center justify-center text-rose-600 mb-4 shadow-xs">
            <AlertCircle className="w-8 h-8" />
          </div>
          <h2 className="text-xl font-bold text-slate-900 mb-2">
            {this.props.fallbackTitle || 'Something went wrong rendering this view'}
          </h2>
          <p className="text-sm text-slate-600 max-w-md mb-3">
            {this.state.error?.message || 'An unexpected rendering error occurred.'}
          </p>
          <div className="flex items-center gap-3 mt-4">
            <button
              onClick={this.handleReset}
              className="px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs shadow-md transition-all flex items-center gap-2 cursor-pointer"
            >
              <RotateCw className="w-3.5 h-3.5" />
              <span>Retry View</span>
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
