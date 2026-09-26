import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "./AuthProvider";
import { ToastProvider } from "./components/Toast";

export const metadata: Metadata = {
  title: "Causor",
  description: "Agente operacional juridico"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <head>
        {/* Aplica o tema salvo antes da hidratação para evitar flash de tema. */}
        <script
          dangerouslySetInnerHTML={{
            __html:
              "(function(){try{if(localStorage.getItem('causor.theme')==='dark'){document.documentElement.dataset.theme='dark';}}catch(e){}})();"
          }}
        />
      </head>
      <body>
        <ToastProvider>
          <AuthProvider>{children}</AuthProvider>
        </ToastProvider>
      </body>
    </html>
  );
}
