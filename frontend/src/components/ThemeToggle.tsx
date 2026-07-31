import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Sun, Moon } from "lucide-react";
import { useI18n } from "@/i18n";

/** Koyu/açık tema arasında geçiş yapan yuvarlak düğme (başlıkta). */
const ThemeToggle = ({ className = "" }: { className?: string }) => {
  const { resolvedTheme, setTheme } = useTheme();
  const { t } = useI18n();
  // next-themes ilk render'da çözümlenmiş temayı bilmez; ikon zıplamasın diye
  // bağlanana kadar nötr gösterilir.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const isDark = mounted && resolvedTheme === "dark";
  const label = isDark ? t("nav.themeLight") : t("nav.themeDark");

  return (
    <button
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label={label}
      title={label}
      className={`w-9 h-9 rounded-full bg-muted/60 flex items-center justify-center text-foreground hover:bg-muted transition-colors ${className}`}
    >
      {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
    </button>
  );
};

export default ThemeToggle;
