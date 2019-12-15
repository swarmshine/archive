import os
import re
import time
from argparse import ArgumentParser

import requests
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

host = ""
WAIT_PAGE_TIME = 10

parser = ArgumentParser()
parser.add_argument("-l", "--login", type=str, required=True)
parser.add_argument("-p", "--password", type=str, required=True)
parser.add_argument("-x", "--proxy", type=str, required=False)

#for tor browser use: -x 185.130.105.66:11084

args = parser.parse_args()
login = args.login
password = args.password

options = webdriver.ChromeOptions()

# socks5://user:pass@host:port
proxies = None
if args.proxy is not None:
    proxies = dict(
        http='socks5://' +  args.proxy + '&',
        https='socks5://' + args.proxy +'&'
    )
    options.add_argument("--proxy-server=socks5://" + args.proxy)

driver = webdriver.Chrome(executable_path=ChromeDriverManager().install(), chrome_options=options)


def normalizeDirFileName(name: str) -> str:
    name = re.sub('[^0-9a-zA-Zа-яА-Я]+', '_', name)
    name = re.sub('[_]+', ' ', name)
    name = name.strip()
    if len(name) > 254:
        name = name[0:254]
    return name


def fileLink(id: str, page: int) -> str:
    return f"http://eais.tatar.ru/Pages/ImageFilePart.ashx?Crop=False&Id={id}&Page={page}&Zoom=1"


def get(link: str) -> requests.Response:
    for i in range(0, 5):
        try:
            session = requests.Session()
            for cookie in driver.get_cookies():
                session.cookies.set(cookie['name'], cookie['value'])
            if proxies is not None:
                session.proxies = proxies
            resp = session.get(link, timeout=120)
            return resp
        except Exception as e:
            print(f"Failed to download. Attempt {i}")

def downloadImage(id: str, page: int, dir) -> bool:
    print(f"Download file {id} page {page} into:\n{dir}")
    fileName = f"id-{id}-page-{page}"
    if any(fileName in item for item in os.listdir(dir)):
        print(f"File {fileName} already downloaded. Skip.")
        return True

    print(f"Download file: {id}, page: {page}")
    link = fileLink(id, page)
    resp = get(link)

    print(f"Download status for file {id}, page {page}: {resp.status_code}")

    contentType = ""
    if 'content-type' in resp.headers:
        contentType = resp.headers['content-type']
    contentType = contentType.lower()

    contentLength = 0
    if 'Content-Length' in resp.headers:
        contentLength = int(resp.headers['Content-Length'])

    print(f"File: {fileName} length: {contentLength} content-type: {contentType}")

    ext = "jpg"
    if "jpeg" in contentType or "jpg" in contentType:
        ext = "jpg"
    elif "png" in contentType:
        ext = "png"
    elif "gif" in contentType:
        ext = "gif"

    if resp.status_code == 200 and contentLength > 0:
        with open(os.path.join(dir, f"{fileName}.{ext}"), "wb") as file:
            resp.raw.decode_content = True
            file.write(resp.content)
            return True

    return False


class Ref:
    def __init__(self, name: str, id: str):
        self.name: str = name
        self.id: str = id

    def __repr__(self):
        return f"{{{self.name}-{self.id}}}"

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.name == other.name and self.id == other.id
        else:
            return False


class FileNode:

    def __init__(self, id: str, type: str):
        self.id: str = id
        self.type: str = type

    def __repr__(self):
        return f"{{{self.id}-{self.type}}}"

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.id == other.id and self.type == other.type
        else:
            return False


def parseBreadCrumbs() -> [str]:
    return [node.strip() for node in driver.find_element_by_id('breadCrumbsPnl').text.split("\n") if len(node) > 0]


def waitBreadCrumbsUpdate(curBreadCrumbs: [str]) -> [str]:
    start = time.time()
    ensureEmptyForRealRetry = True
    newBreadCrumbs: [str] = []

    while time.time() - start < WAIT_PAGE_TIME:
        try:
            newBreadCrumbs = parseBreadCrumbs()
            if ensureEmptyForRealRetry and len(newBreadCrumbs) == 0:
                print("empty bread crumbs, retry once")
                ensureEmptyForRealRetry = False
                time.sleep(1)
                continue

            if newBreadCrumbs != curBreadCrumbs:
                print(f"bread crumbs updated: {curBreadCrumbs} -> {newBreadCrumbs}")
                return newBreadCrumbs
            else:
                print(f"bread crumbs still the same, retry: {newBreadCrumbs}")
        except:
            print(f"failed to parse bread crumbs, retry: {newBreadCrumbs}")

        print(f"left to wait {start + WAIT_PAGE_TIME - time.time()}s")
        time.sleep(1)

    print(f"Failed to wait breadCrubgs update: {curBreadCrumbs} -> {newBreadCrumbs}")
    return newBreadCrumbs


def parseFiles() -> [str]:
    ids = [idElm.get_attribute('value') for idElm in driver.find_elements_by_css_selector(
        "input[id*=MainPlaceHolder__storageFilesGridControl__gStorageFiles__hfStorageFileId_]")]
    # Jpeg, Pdf
    formats = [formatElm.get_attribute('value') for formatElm in driver.find_elements_by_css_selector(
        "input[id*=MainPlaceHolder__storageFilesGridControl__gStorageFiles__hfFileFormat_]")]

    files: [FileNode] = []

    for i in range(0, len(ids)):
        files.append(FileNode(ids[i], formats[i]))

    return files


def waitFilesUpdate(prevFileNodes: [FileNode]) -> [FileNode]:
    start = time.time()
    ensureEmptyForRealRetry = True
    newFileNodes: [FileNode] = []

    while time.time() - start < WAIT_PAGE_TIME:
        try:
            newFileNodes = parseFiles()
            if ensureEmptyForRealRetry and len(newFileNodes) == 0:
                print("empty files, retry once")
                ensureEmptyForRealRetry = False
                time.sleep(1)
                continue

            if newFileNodes != prevFileNodes:
                print(f"file nodes updated: {prevFileNodes} -> {newFileNodes}")
                return newFileNodes
            else:
                print(f"file nodes not updated yet: {prevFileNodes}->{newFileNodes}")
        except:
            print(f"failed to parse files, retry: {newFileNodes}")

        print(f"left to wait {start + WAIT_PAGE_TIME - time.time()}")
        time.sleep(1)

    print(f"Failed to wait file nodes update: {prevFileNodes} -> {newFileNodes}")
    return newFileNodes


def parseRefs() -> [Ref]:
    refs: [Ref] = []
    for node in driver.find_elements_by_css_selector("a[id*=MainPlaceHolder_ArchiveGridView_NameLnk_]"):
        refs.append(Ref(str(node.text).strip(), str(node.get_attribute('id'))))
    return refs


def waitRefsUpdate(curRefs: [Ref]) -> [Ref]:
    start = time.time()
    ensureEmptyForRealRetry = True
    newRefs: [Ref] = []

    while time.time() - start < WAIT_PAGE_TIME:
        try:
            newRefs = parseRefs()
            if ensureEmptyForRealRetry and len(newRefs) == 0:
                print("empty refs, retry once")
                ensureEmptyForRealRetry = False
                time.sleep(1)
                continue

            if newRefs != curRefs:
                print(f"refs updated: {curRefs} -> {newRefs}")
                return newRefs
            else:
                print("refs still the same, retry")
        except:
            print("failed to parse refs, retry")

        print(f"left to wait {start + WAIT_PAGE_TIME - time.time()}")
        time.sleep(1)

    print(f"Failed to wait refs update: {curRefs} -> {newRefs}")
    return newRefs


def clickLastBreadCrumbElement():
    try:
        # css: #breadCrumbsPnl a
        upElm = driver.find_element_by_xpath("(//*[@id='breadCrumbsPnl']//a)[last()]")

        print(f"Click up: {upElm.text}")
        upElm.click()
    except Exception as e:
        print(f"Failed to find last bread crumb:\n{e}")


def buildDirectory(path: [str]) -> str:
    dirPath = os.path.join(*[normalizeDirFileName(node) for node in path])
    print(f"create: {dirPath}")
    os.makedirs(dirPath, exist_ok=True)
    return dirPath


class PageIterator:
    def __init__(self) -> None:
        super().__init__()
        self.breadCrumbs: [str] = parseBreadCrumbs()
        self.savePath: str = buildDirectory(self.breadCrumbs)

        self.totalPages: int = int(driver.find_element_by_id('MainPlaceHolder__pagingControl__lTotalPages').text)
        self.page: int = 1

    def waitUpdate(self) -> None:
        raise NotImplementedError

    def processPage(self) ->None:
        raise NotImplementedError

    def iterateThrougPages(self):
        """
        Invoke processPage lambda on each of pages of current document
        Lambda is responsible to return browser to the same view but not necessary with same page
        """
        print(f"Total pages: {self.totalPages} for {self.breadCrumbs}")

        while self.page in range(1, self.totalPages + 1):
            print(f"Process page: {self.page}")

            self.navigateToCurrentPage()
            self.processPage()
            self.page += 1


    def navigateToCurrentPage(self):
        curPage = int(driver.find_element_by_id('MainPlaceHolder__pagingControl__tbCurrentPage').get_attribute('value'))
        if self.totalPages > 1 and curPage != self.page:
            print(f"Set page {self.page} of {self.totalPages}")
            pageElm = driver.find_element_by_id('MainPlaceHolder__pagingControl__tbCurrentPage')
            pageElm.clear()
            pageElm.send_keys(str(self.page))
            pageElm.send_keys(Keys.ENTER)

            self.waitUpdate()


class FileNodesPageIterator(PageIterator):
    def __init__(self):
        super().__init__()
        self.fileNodes: [FileNode] = waitFilesUpdate([])

    def waitUpdate(self) -> None:
        self.fileNodes = waitFilesUpdate(self.fileNodes)

    def processPage(self) -> None:
        download_file_nodes(self.fileNodes, self.savePath)


def save_file_downloaded_marker(id: str, saveDir: str):
    with open(os.path.join(saveDir, f"{id}.saved"), "a") as file:
        return True


def check_file_downloaded_marker(id: str, saveDir: str) -> bool:
    return os.path.isfile(os.path.join(saveDir, f"{id}.saved"))


def download_file_nodes(fileNodes: [FileNode], savePath: str):
    """
    Simplified version: do not parse file page count and name from site.
    Detect number of pages by trying to download all that we can
    """
    os.makedirs(savePath, exist_ok=True)

    for file in fileNodes:
        if check_file_downloaded_marker(file.id, savePath):
            print(f"Skip processed file {file.id} for dir \n{savePath}.")
            continue

        if file.type == "Pdf":
            for i in range(0, 3000):
                res = downloadImage(file.id, i, savePath)
                if not res:
                    break
        else:
            downloadImage(file.id, 0, savePath)

        save_file_downloaded_marker(file.id, savePath)


class NodesPageIterator(PageIterator):
    def __init__(self):
        super().__init__()
        self.refs: [Ref] = parseRefs()

    def waitUpdate(self) -> None:
        self.refs = waitRefsUpdate(self.refs)

    def processPage(self) -> None:
        if len(self.refs) == 0:
            print("No nodes.")
            return

        print("Found nodes:")
        for ref in self.refs:
            print(f"{ref.name}")

        # Search for `view file list` buttons on the given page
        # Iterate over all such buttons
        # For each button:
        #     - click on button and open file list
        #     - process file list
        #     - move back to the given page

        viewFileListElmIds = [file.get_attribute('id') for file in driver.find_elements_by_css_selector("a[id*=MainPlaceHolder_ArchiveGridView_StorageFilesViewerBtn_]")]
        print(f"Found {len(viewFileListElmIds)} file views")
        for viewFileListElmId in viewFileListElmIds:

            print("Open file list")
            driver.find_element_by_id(viewFileListElmId).click()
            fileListBreadCrumbs = waitBreadCrumbsUpdate(self.breadCrumbs)

            FileNodesPageIterator().iterateThrougPages()

            clickLastBreadCrumbElement()

            waitBreadCrumbsUpdate(fileListBreadCrumbs)
            waitRefsUpdate([])
            self.navigateToCurrentPage()

        for ref in self.refs:
            try:
                print(f"Click down {ref.name}")
                driver.find_element_by_id(ref.id).click()
            except Exception as e:
                print(f"Failed to find ref {ref}:\n{e}")

            waitBreadCrumbsUpdate(self.breadCrumbs)
            waitRefsUpdate(self.refs)

            browse_nodes()

            prevCrumbs = parseBreadCrumbs()
            prevRefs = parseRefs()

            clickLastBreadCrumbElement()

            waitBreadCrumbsUpdate(prevCrumbs)
            waitRefsUpdate(prevRefs)
            self.navigateToCurrentPage()


def browse_nodes():
    iter = NodesPageIterator()

    if check_file_downloaded_marker("dir", iter.savePath):
        print(f"Dir already processed: {iter.savePath}")
        return

    print(f"Iterate within node: {iter.breadCrumbs}")
    iter.iterateThrougPages()

    save_file_downloaded_marker("dir", iter.savePath)


driver.get("http://eais.tatar.ru")

driver.find_element_by_id("LoginPnl_UserName").send_keys(login)
driver.find_element_by_id("LoginPnl_Password").send_keys(password)

driver.find_element_by_id("Login").click()
# driver.find_element_by_id("LoginPnl_AnonymousLogin").click()

driver.get("http://eais.tatar.ru/Pages/FundsList/FundsList.aspx")

input("Please open required section and press Enter to continue: ")

print("Detecting page type")

waitBreadCrumbsUpdate([])

refs = parseRefs()
files = parseFiles()

print(f"refs: {refs}")
print(f"files: {files}")

if len(files) > 0:
    print("Browse file list")
    FileNodesPageIterator().iterateThrougPages()
else:
    print("Browse node list")
    browse_nodes()

driver.close()
