interface ErrorAlertProps {
  message: string;
}

export function ErrorAlert({ message }: ErrorAlertProps) {
  return <div className="alert alert-error" role="alert">{message}</div>;
}

interface WarningAlertProps {
  message: string;
}

export function WarningAlert({ message }: WarningAlertProps) {
  return <div className="alert alert-warning" role="status">{message}</div>;
}

interface InfoAlertProps {
  message: string;
}

export function InfoAlert({ message }: InfoAlertProps) {
  return <div className="alert alert-info" role="status">{message}</div>;
}
