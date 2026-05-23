import { ReactNode } from "react";

interface LayoutProps {
  header: ReactNode;
  left: ReactNode;
  center: ReactNode;
  right: ReactNode;
  footer?: ReactNode;
}

function Layout({ header, left, center, right, footer }: LayoutProps) {
  return (
    <div className="app-shell">
      {header}
      <main className="dashboard-grid">
        <aside className="left-rail">{left}</aside>
        <section className="center-stage">{center}</section>
        <aside className="right-rail">{right}</aside>
      </main>
      {footer}
    </div>
  );
}

export default Layout;
