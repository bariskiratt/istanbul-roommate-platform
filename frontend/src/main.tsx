import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./index.css";

// Sayfalar ayrı parçalar halinde yükleniyor (bkz. App.tsx). Yeni bir yayından
// önce açılmış bir sekme, artık sunucuda olmayan eski parçayı ister ve
// sayfa boş kalır. Bir kez yenilemek yeni sürümü getirir. Parça gerçekten
// bozuksa sonsuz döngüye girmemek için 30 saniyede en fazla bir yenileme.
window.addEventListener("vite:preloadError", () => {
  const KEY = "chunk-reload-at";
  try {
    const last = Number(sessionStorage.getItem(KEY) ?? 0);
    if (Date.now() - last < 30_000) return;
    sessionStorage.setItem(KEY, String(Date.now()));
  } catch {
    return;
  }
  window.location.reload();
});

createRoot(document.getElementById("root")!).render(<App />);
