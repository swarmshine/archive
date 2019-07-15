import requests
import re
import os
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver import remote
import time
from selenium.webdriver.common.keys import Keys

from argparse import ArgumentParser

host = ""
WAIT_PAGE_TIME = 10

parser = ArgumentParser()
parser.add_argument("-l", "--login", type=str, required=True)
parser.add_argument("-p", "--password", type=str, required=True)

args = parser.parse_args()
login = args.login
password = args.password

driver = webdriver.Chrome(ChromeDriverManager().install())


def normalizeDirFileName(name: str) -> str:
    name = re.sub('[^0-9a-zA-Zа-яА-Я]+', '_', name)
    name = re.sub('[_]+', ' ', name)
    name = name.strip()
    return name


def fileLink(id: str, page: int) -> str:
    return f"http://eais.tatar.ru/Pages/ImageFilePart.ashx?Crop=False&Id={id}&Page={page}&Zoom=1"


def get(link: str) -> requests.Response:
    session = requests.Session()
    for cookie in driver.get_cookies():
        session.cookies.set(cookie['name'], cookie['value'])

    resp = session.get(link)
    return resp


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


def parseDocId(content: str) -> str:
    return re.search("Id=([\\w\\d]{8}-[\\w\\d]{4}-[\\w\\d]{4}-[\\w\\d]{4}-[\\w\\d]{12})[^\\d\\w]", content).group(1)


class Ref:
    name: str
    id: str

    def __init__(self, name: str, id: str):
        self.name = name
        self.id = id

    def __repr__(self):
        return f"{{{self.name}-{self.id}}}"

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.name == other.name and self.id == other.id
        else:
            return False


class FileNode:
    id: str
    type: str

    def __init__(self, id: str, type: str):
        self.id = id
        self.type = type

    def __repr__(self):
        return f"{{{self.id}-{self.type}}}"

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.id == other.id and self.type == other.type
        else:
            return False


def parseBreadCrubms() -> [str]:
    return [node.strip() for node in driver.find_element_by_id('breadCrumbsPnl').text.split("\n") if len(node) > 0]


def waitBreadCrumbsUpdate(curBreadCrumbs: [str]) -> [str]:
    start = time.time()
    ensureEmptyForRealRetry = True
    newBreadCrumbs :[str] = []

    while time.time() - start < WAIT_PAGE_TIME:
        try:
            newBreadCrumbs = parseBreadCrubms()
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

def browseFiles():

    breadCrubms = parseBreadCrubms()
    savePath = buildDirectory(breadCrubms)

    fileNodes: [FileNode] = waitFilesUpdate([])

    totalPages = int(driver.find_element_by_id('MainPlaceHolder__pagingControl__lTotalPages').text)
    print(f"File list total pages: {totalPages}")

    for page in range(1, totalPages + 1):
        curPage = int(
            driver.find_element_by_id('MainPlaceHolder__pagingControl__tbCurrentPage').get_attribute('value'))

        if totalPages > 1 and curPage != page:
            print(f"Set file list page {page} of {totalPages}")
            pageElm = driver.find_element_by_id('MainPlaceHolder__pagingControl__tbCurrentPage')
            pageElm.clear()
            pageElm.send_keys(str(page))
            pageElm.send_keys(Keys.ENTER)
            fileNodes = waitFilesUpdate(fileNodes)

        downloadFileNodes(fileNodes, savePath)


def browseFileLists(savePath: str):
    """
    Search for `view file list` buttons on the given page
    Iterate over all such buttons
    For each button:
        - click on button and open file list
        - process file lists
        - move back to the given page
    """
    viewFileListElmIds = [file.get_attribute('id') for file in driver.find_elements_by_css_selector(
        "a[id*=MainPlaceHolder_ArchiveGridView_StorageFilesViewerBtn_]")]
    print(f"Found {len(viewFileListElmIds)} file views")
    for fileElmId in viewFileListElmIds:

        breadCrumbs = parseBreadCrubms()

        print("Open file list")
        driver.find_element_by_id(fileElmId).click()
        newBreadCrumbs = waitBreadCrumbsUpdate(breadCrumbs)

        browseFiles()

        clickLastBreadCrumbElement()

        waitBreadCrumbsUpdate(newBreadCrumbs)
        waitRefsUpdate([])


def saveFileDownloadedMarker(id: str, saveDir: str):
    with open(os.path.join(saveDir, f"{id}.saved"), "a") as file:
        return True


def checkFileDownloadedMarker(id: str, saveDir: str) -> bool:
    return os.path.isfile(os.path.join(saveDir, f"{id}.saved"))


def downloadFileNodes(fileNodes: [FileNode], savePath: str):
    """
    Simplified version: do not parse file page count and name from site.
    Detect number of pages by trying to download all that we can
    """
    os.makedirs(savePath, exist_ok=True)

    for file in fileNodes:
        if checkFileDownloadedMarker(file.id, savePath):
            print(f"Skip processed file {file.id} for dir \n{savePath}.")
            continue

        if file.type == "Pdf":
            for i in range(0, 3000):
                res = downloadImage(file.id, i, savePath)
                if not res:
                    break
        else:
            downloadImage(file.id, 0, savePath)

        saveFileDownloadedMarker(file.id, savePath)

def browseNodes():
    breadCrubms = parseBreadCrubms()
    refs = parseRefs()

    fileListSaveDir = buildDirectory(breadCrubms)

    if checkFileDownloadedMarker("dir", fileListSaveDir):
        print(f"Dir already processed: {fileListSaveDir}")
        return

    totalPages = int(driver.find_element_by_id('MainPlaceHolder__pagingControl__lTotalPages').text)

    print(f"Parse page: {breadCrubms}")

    for page in range(1, totalPages + 1):
        print(f"Process nodes page {page}")

        curPage = int(driver.find_element_by_id('MainPlaceHolder__pagingControl__tbCurrentPage').get_attribute('value'))

        if totalPages > 1 and curPage != page:
            print(f"Set nodes page {page} of {totalPages}")
            pageElm = driver.find_element_by_id('MainPlaceHolder__pagingControl__tbCurrentPage')
            pageElm.clear()
            pageElm.send_keys(str(page))
            pageElm.send_keys(Keys.ENTER)

            refs = waitRefsUpdate(refs)

        if len(refs) > 0:
            print("Found nodes:")
            for ref in refs:
                print(f"{ref.name}")

            browseFileLists(fileListSaveDir)

            for ref in refs:
                try:
                    print(f"Click down {ref.name}")
                    driver.find_element_by_id(ref.id).click()
                except Exception as e:
                    print(f"Failed to find ref {ref}:\n{e}")

                waitBreadCrumbsUpdate(breadCrubms)
                waitRefsUpdate(refs)

                browseNodes()

                prevCrumbs = parseBreadCrubms()
                prevRefs = parseRefs()

                clickLastBreadCrumbElement()

                waitBreadCrumbsUpdate(prevCrumbs)
                waitRefsUpdate(prevRefs)

                if totalPages > 1 and curPage != page:
                    print(f"Set nodes page back to {page} of {totalPages}")
                    pageElm = driver.find_element_by_id('MainPlaceHolder__pagingControl__tbCurrentPage')
                    pageElm.clear()
                    pageElm.send_keys(str(page))
                    pageElm.send_keys(Keys.ENTER)
                    refs = waitRefsUpdate(refs)

        else:
            print("No nodes.")

    saveFileDownloadedMarker("dir", fileListSaveDir)



driver.get("http://eais.tatar.ru")
driver.find_element_by_id("LoginPnl_UserName").send_keys(login)
driver.find_element_by_id("LoginPnl_Password").send_keys(password)

driver.find_element_by_id("Login").click()
# driver.find_element_by_id("LoginPnl_AnonymousLogin").click()

driver.get("http://eais.tatar.ru/Pages/FundsList/FundsList.aspx")

input("Please open required section and press Enter to continue: ")

print("Detecting page type")
breadCrubms = waitBreadCrumbsUpdate([])

refs = parseRefs()
files = parseFiles()

print(f"refs: {refs}")
print(f"files: {files}")

if len(files) > 0:
    print("Browse file list")
    browseFiles()
else:
    print("Browse node list")
    browseNodes()


driver.close()
