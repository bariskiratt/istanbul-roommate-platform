import { useNavigate } from "react-router-dom";
import { X } from "lucide-react";
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
          className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/40 backdrop-blur-sm"
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.9, opacity: 0 }}
            className="bg-card rounded-2xl border border-border shadow-[0_20px_60px_-20px_rgba(15,20,50,0.45)] max-w-sm w-full p-7 space-y-5 relative"
          >
            <button
              onClick={() => handleNavigate("/")}
              aria-label={t("common.close")}
              className="absolute top-4 right-4 w-9 h-9 rounded-full flex items-center justify-center text-muted-foreground hover:bg-muted"
            >
              <X className="w-4 h-4" />
            </button>

            <h2 className="text-[1.9rem] leading-tight text-foreground pr-10">{t("gate.title")}</h2>
            <p className="text-muted-foreground leading-relaxed">{t("gate.desc")}</p>

            <div className="space-y-3 pt-2">
              <Button
                onClick={() => handleNavigate("/onboarding")}
                size="lg"
                className="w-full h-12 text-base"
              >
                {t("gate.signup")}
              </Button>
              <Button
                variant="ghost"
                onClick={() => handleNavigate("/login")}
                size="lg"
                className="w-full h-12 text-base"
              >
                {t("gate.login")}
              </Button>
            </div>

            <p className="text-[13px] text-muted-foreground">{t("gate.note")}</p>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default AuthGate;
