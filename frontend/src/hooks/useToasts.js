import { useCallback, useState } from "react";

let idCounter = 0;

export function useToasts() {
  const [toasts, setToasts] = useState([]);

  const pushToast = useCallback((message, variant = "info") => {
    const id = ++idCounter;
    setToasts((prev) => [...prev, { id, message, variant }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4200);
  }, []);

  const dismissToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return { toasts, pushToast, dismissToast };
}
