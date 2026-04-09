import { Component, type ErrorInfo, type ReactNode } from "react";

import { Alert } from "@heroui/react/alert";
import { Button } from "@heroui/react/button";

type DashboardErrorBoundaryProps = {
  children: ReactNode;
  title: string;
  body: string;
  reloadLabel: string;
  homeLabel: string;
};

type State = { error: Error | null };

export class DashboardErrorBoundary extends Component<DashboardErrorBoundaryProps, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("DashboardErrorBoundary", error, info);
  }

  render() {
    const { children, title, body, reloadLabel, homeLabel } = this.props;
    if (this.state.error) {
      return (
        <div className="flex min-h-dvh flex-col items-center justify-center gap-6 bg-slate-50 p-6 dark:bg-slate-950">
          <Alert.Root status="danger" className="max-w-md">
            <Alert.Indicator />
            <Alert.Content>
              <Alert.Title>{title}</Alert.Title>
              <Alert.Description>{body}</Alert.Description>
            </Alert.Content>
          </Alert.Root>
          <div className="flex flex-wrap justify-center gap-2">
            <Button
              variant="primary"
              onPress={() => {
                window.location.reload();
              }}
            >
              {reloadLabel}
            </Button>
            <Button
              variant="secondary"
              onPress={() => {
                window.location.hash = "#/";
                this.setState({ error: null });
              }}
            >
              {homeLabel}
            </Button>
          </div>
        </div>
      );
    }
    return children;
  }
}
