import type { WorldsConfig } from './types';

async function responseJson(response: Response, message: string) {
  if (!response.ok) throw new Error(message);
  return response.json();
}

export async function refetchWorldConfigOnRevisionMismatch(
  api: string,
  roomId: string,
  current: WorldsConfig,
  fetcher: typeof fetch = fetch,
): Promise<WorldsConfig | null> {
  const room = await responseJson(
    await fetcher(`${api}/worlds/${roomId}`, { cache: 'no-store' }),
    'World config request failed.',
  );
  if (room.revision === current.revision) return null;

  const refreshed: WorldsConfig = await responseJson(
    await fetcher(`${api}/worlds?refresh=${Date.now()}`, { cache: 'no-store' }),
    'World config refresh failed.',
  );
  const verifiedRoom = await responseJson(
    await fetcher(`${api}/worlds/${roomId}?refresh=${Date.now()}`, { cache: 'no-store' }),
    'World config retry failed.',
  );
  if (verifiedRoom.revision !== refreshed.revision) throw new Error('World configuration is out of sync. Reload to retry.');
  return refreshed;
}
