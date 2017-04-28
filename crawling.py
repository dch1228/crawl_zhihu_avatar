import asyncio
import os

import aiohttp


class Crawler:
    _access_token = ""

    _headers = {
        "x-app-za": "OS=iOS&Release=10.2.1&Model=iPhone9,2&VersionName=3.34.0&VersionCode=596&Width=1125&Height=2001",
        "X-API-Version": "3.0.52",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "osee2unifiedRelease/3.34.0 (iPhone; iOS 10.2.1; Scale/3.00)",
        "X-UDID": "",
        "X-APP-Build": "release",
        "X-APP-VERSION": "3.34.0",
        "Authorization": _access_token
    }

    _base_url = "https://api.zhihu.com/"

    _avatar_path = "./avatar/"

    def __init__(self, loop=None):
        self._loop = loop or asyncio.get_event_loop()
        self._session = aiohttp.ClientSession(loop=self._loop)
        self.users_q = asyncio.Queue(loop=self._loop)

        self.done = set()

        self.add_url(self._base_url + "people/{user_id}/followees")

    async def process(self, url):
        try:
            print(">>>>", url)
            resp = await self._session.get(url,
                                           headers=self._headers)
        except aiohttp.ClientError as err:
            print("fetch url: {} fail, err:{}".format(url, err))
            return

        if resp.status != 200:
            return

        json_data = await resp.json()
        paging = json_data["paging"]
        if not paging["is_end"]:
            self.add_url(paging["next"])

        users = json_data["data"]
        for user in users:
            self.add_url(self._base_url + "people/{}/followees".format(user["id"]))
            if user["gender"] == 0:
                await self.download_avatar(user["name"], user["avatar_url"])

    async def download_avatar(self, username, url):
        filename = "{}.jpg".format(username)
        path = "{}{}".format(self._avatar_path, filename)
        url = url.replace("_s", "_hd")

        if os.path.exists(path):
            return

        print("download: {}".format(filename))

        with open(path, 'wb') as f:
            async with self._session.get(url) as resp:
                while True:
                    chunk = await resp.content.read(100)
                    if not chunk:
                        break
                    f.write(chunk)
        print("done.")

    def add_url(self, url):
        if url not in self.done:
            self.users_q.put_nowait(url)

    async def work(self):
        try:
            while True:
                user_url = await self.users_q.get()
                await self.process(user_url)
                self.users_q.task_done()

                file_count = len([i for i in os.listdir(self._avatar_path) if os.path.isfile(i)])
                if file_count >= 10000:
                    break
        except asyncio.CancelledError:
            pass

    def close(self):
        self._session.close()

    async def crawl(self):
        workers = [asyncio.Task(self.work(), loop=self._loop)
                   for _ in range(16)]
        await self.users_q.join()
        for w in workers:
            w.cancel()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()

    crawler = Crawler()

    loop.run_until_complete(crawler.crawl())

    crawler.close()

    loop.close()
