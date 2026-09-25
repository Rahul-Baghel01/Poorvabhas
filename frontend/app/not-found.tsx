import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 p-6 text-center">
      <p className="label-tech">Error 404</p>
      <h1 className="text-[28px] font-semibold">Page not found</h1>
      <p className="text-[14px] text-fg-2">The page you requested does not exist in Poorvabhas.</p>
      <Link href="/" className="mt-2 text-cyan hover:underline">
        Return to the command center
      </Link>
    </div>
  );
}
