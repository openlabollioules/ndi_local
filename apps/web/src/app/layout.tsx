import "./globals.css";

export const metadata = {
  title: "Naval Data Intelligence",
  description: "Assistant NL-to-SQL local",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fr" dir="ltr">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
