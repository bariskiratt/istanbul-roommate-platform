import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import {
  type ApiUser,
  clearToken,
  fetchMe,
  getToken,
  logoutApi,
  setToken,
} from "@/lib/api";

interface AuthContextType {
  isLoggedIn: boolean;
  user: ApiUser | null;
  /** OTP doğrulamasından dönen token + kullanıcıyla oturumu başlatır. */
  login: (token: string, user: ApiUser) => void;
  logout: () => void;
  /** Profil güncellemesi sonrası context'teki kullanıcıyı tazeler. */
  setUser: (user: ApiUser) => void;
}

const AuthContext = createContext<AuthContextType>({
  isLoggedIn: false,
  user: null,
  login: () => {},
  logout: () => {},
  setUser: () => {},
});

export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUserState] = useState<ApiUser | null>(null);
  const [isLoggedIn, setIsLoggedIn] = useState(() => getToken() !== null);

  // Sayfa yenilenince token'dan kullanıcıyı geri yükle; token geçersizse temizle.
  useEffect(() => {
    if (!getToken()) return;
    fetchMe()
      .then(me => {
        setUserState(me);
        setIsLoggedIn(true);
      })
      .catch(() => {
        clearToken();
        setUserState(null);
        setIsLoggedIn(false);
      });
  }, []);

  const login = (token: string, me: ApiUser) => {
    setToken(token);
    setUserState(me);
    setIsLoggedIn(true);
  };

  const logout = () => {
    logoutApi().catch(() => {}); // sunucuya ulaşılamasa da yerelde çıkış yap
    clearToken();
    setUserState(null);
    setIsLoggedIn(false);
  };

  return (
    <AuthContext.Provider value={{ isLoggedIn, user, login, logout, setUser: setUserState }}>
      {children}
    </AuthContext.Provider>
  );
};
