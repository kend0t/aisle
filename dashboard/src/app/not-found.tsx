import Link from "next/link";
import PageMessage from "@/components/PageMessage";
import StatusBar from "@/components/StatusBar";

export default function NotFound() {
  return (
    <>
      <StatusBar state="idle" updatedAt={0} />
      <PageMessage title="No page at this address." actions={<Link href="/">Go to the dashboard</Link>}>
        <p>The dashboard has one page. Check the address, or go back to it.</p>
      </PageMessage>
    </>
  );
}
