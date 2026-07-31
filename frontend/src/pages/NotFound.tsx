import { Link, useLocation } from "react-router-dom";
import { useEffect } from "react";

const NotFound = () => {
  const location = useLocation();

  useEffect(() => {
    console.error("404: olmayan rota:", location.pathname);
  }, [location.pathname]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="text-center space-y-4">
        <h1 className="text-5xl font-semibold text-foreground">404</h1>
        <p className="text-lg text-muted-foreground">Aradığın sayfa bulunamadı.</p>
        <Link to="/" className="inline-block text-primary font-semibold underline underline-offset-4 hover:opacity-80">
          Ana sayfaya dön
        </Link>
      </div>
    </div>
  );
};

export default NotFound;
