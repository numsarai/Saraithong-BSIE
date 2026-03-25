import { Component, type ReactNode } from 'react'

interface Props { children: ReactNode }
interface State { error: Error | null }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex items-center justify-center min-h-screen bg-bg text-text p-8">
          <div className="max-w-md text-center space-y-4">
            <h1 className="text-xl font-bold text-danger">Something went wrong</h1>
            <p className="text-muted text-sm font-mono">{this.state.error.message}</p>
            <button
              onClick={() => { this.setState({ error: null }); window.location.reload() }}
              className="px-4 py-2 bg-accent text-black rounded-lg font-semibold text-sm hover:bg-accent2 transition-all cursor-pointer"
            >
              Reload App
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
