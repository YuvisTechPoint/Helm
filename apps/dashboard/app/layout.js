import "./globals.css";
import Sidebar from "../components/Sidebar";
import Topbar from "../components/Topbar";

export const metadata = {
  title: "YouTube Channel Engine",
  description: "Control plane for the autonomous faceless YouTube channel engine.",
};

export const viewport = {
  themeColor: "#09090b",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;550;600;650;700&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <div className="shell">
          <Sidebar />
          <div className="main">
            <Topbar />
            <main className="content">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
