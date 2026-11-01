import './style.css';
import './world.css';
import './theme.css';
export const metadata = {title: 'Beyond — People, Stories, New Worlds', description: 'A cozy, magical event experience where meaningful connections lead to new perspectives.'};
export default function Layout({children}: {children: React.ReactNode}) { return <html lang="en"><body>{children}</body></html>; }
