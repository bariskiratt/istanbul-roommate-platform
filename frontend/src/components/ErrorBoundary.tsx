import { Component, type ErrorInfo, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import SiteBar from "@/components/layout/SiteBar";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/i18n";

/**
 * Kök seviyedeki hata sınırı.
 *
 * Neden: bir sayfa çizilirken fırlayan tek bir hata (beklenmedik bir API
 * yanıtı, eksik bir alan) React'te bütün ağacı söker ve kullanıcı bembeyaz
 * bir ekranla kalır: ne menü ne geri dönecek bir düğme. Sınır o hatayı
 * yakalar, yerine yenileme ve ana sayfa düğmeleri olan bir sayfa koyar.
 *
 * Yalnızca çizim sırasındaki hataları yakalar; olay işleyicilerdeki ve
 * sözlerdeki (Promise) hatalar zaten toast ile gösteriliyor.
 *
 * Sınır App.tsx'te BrowserRouter'ın içinde, Routes'un dışındadır; başka
 * sayfaya geçince (resetKey = adres) kendiliğinden sıfırlanır. Router'a bu
 * yüzden bağlı: dosyanın varsayılan dışa aktarımı adresi okuyan sarmalayıcı.
 */
interface Props {
  children: ReactNode;
  /** Değişince sınır hatayı unutur (ör. adres). */
  resetKey?: string;
}

interface State {
  error: Error | null;
  resetKey?: string;
}

class Boundary extends Component<Props, State> {
  state: State = { error: null, resetKey: this.props.resetKey };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  static getDerivedStateFromProps(props: Props, state: State): Partial<State> | null {
    if (props.resetKey !== state.resetKey) {
      return { error: null, resetKey: props.resetKey };
    }
    return null;
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Sayfa çizilirken hata:", error, info.componentStack);
  }

  render() {
    if (this.state.error) return <CrashScreen />;
    return this.props.children;
  }
}

const CrashScreen = () => {
  const { t } = useI18n();
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <SiteBar />
      <main className="flex-1 w-full max-w-xl mx-auto px-5 py-16 md:py-24" role="alert">
        <h1 className="font-display text-4xl md:text-5xl leading-tight font-semibold text-foreground">
          {t("crash.title")}
        </h1>
        <p className="mt-4 text-lg text-muted-foreground">{t("crash.text")}</p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Button size="lg" className="h-12 text-base" onClick={() => window.location.reload()}>
            {t("crash.reload")}
          </Button>
          {/* Tam sayfa geçişi: bozuk durumu bellekte taşımadan baştan kurar. */}
          <Button asChild size="lg" variant="outline" className="h-12 text-base">
            <a href="/">{t("notfound.home")}</a>
          </Button>
        </div>
      </main>
    </div>
  );
};

const ErrorBoundary = ({ children }: { children: ReactNode }) => {
  const { pathname } = useLocation();
  return <Boundary resetKey={pathname}>{children}</Boundary>;
};

export default ErrorBoundary;
