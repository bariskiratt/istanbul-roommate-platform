import { useNavigate } from "react-router-dom";
import { Lock, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { motion, AnimatePresence } from "framer-motion";
import { useI18n } from "@/i18n";

interface AuthGateProps {
  show: boolean;
  onClose?: () => void;
}

const AuthGate = ({ show, onClose }: AuthGateProps) => {
  const navigate = useNavigate();
  const { t } = useI18n();

  const handleNavigate = (path: string) => {
    // Close modal first, then navigate — prevents loops
    if (onClose) onClose();
    setTimeout(() => navigate(path), 10);
  };

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/40 backdrop-blur-md"
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.9, opacity: 0 }}
            className="bg-card rounded-2xl shadow-xl max-w-sm w-full p-8 text-center space-y-5 relative"
          >
            <button
              onClick={() => handleNavigate("/")}
              className="absolute top-4 right-4 w-8 h-8 rounded-full bg-muted flex items-center justify-center text-muted-foreground hover:bg-muted/80"
            >
              <X className="w-4 h-4" />
            </button>

            <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto">
              <Lock className="w-8 h-8 text-primary" />
            </div>

            <h2 className="text-xl font-bold text-foreground">{t("gate.title")}</h2>
            <p className="text-sm text-muted-foreground">{t("gate.desc")}</p>

            <div className="space-y-3 pt-2">
              <Button
                onClick={() => handleNavigate("/onboarding")}
                className="w-full h-12 rounded-full text-sm font-bold bg-gradient-to-r from-primary to-secondary text-primary-foreground"
              >
                {t("gate.signup")}
              </Button>
              <Button
                variant="ghost"
                onClick={() => handleNavigate("/login")}
                className="w-full h-12 rounded-full text-sm font-medium"
              >
                {t("gate.login")}
              </Button>
            </div>

            <p className="text-[11px] text-muted-foreground">{t("gate.note")}</p>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default AuthGate;
