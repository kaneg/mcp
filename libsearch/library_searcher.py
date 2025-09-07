import requests


class LibSearchClient():
    def __init__(self):
        jwt = self.get_jwt()
        jwt = jwt.replace('"', '')
        self.headers = {
            'Authorization': 'Bearer ' + jwt
        }

    @classmethod
    def get_jwt(cls):
        s = 'https://86sjt-primo.hosted.exlibrisgroup.com.cn/primo_library/libweb/webservices/rest/v1/guestJwt/SJT?isGuest=true&lang=zh_CN&targetUrl=https%253A%252F%252F86sjt-primo.hosted.exlibrisgroup.com.cn%252Fprimo-explore%252Fsearch%253Fquery%253Dany%252Ccontains%252C%2525E9%252587%25258F%2525E5%2525AD%252590%2526tab%253Ddefault_tab%2526search_scope%253Dbook_journal%2526vid%253Dbook%2526offset%253D0&viewId=book'

        rsp = requests.get(s)
        return rsp.text

    def search(self, query, language=None, advanced=False):
        if advanced:
            q = query
        else:
            q = f"any,contains,{query}"

        if language and language.strip():
            q = f"{q},AND;facet_lang,exact,{language.strip()},AND"

        s = f'https://86sjt-primo.hosted.exlibrisgroup.com.cn/primo_library/libweb/webservices/rest/primo-explore/v1/pnxs?acTriggered=false&blendFacetsSeparately=false&citationTrailFilterByAvailability=true&getMore=0&inst=SJT&isCDSearch=false&lang=zh_CN&limit=10&newspapersActive=false&newspapersSearch=false&offset=0&otbRanking=false&pcAvailability=true&q={q}&qExclude=&qInclude=&refEntryActive=false&rtaLinks=true&scope=book_journal&searchInFulltextUserSelection=true&skipDelivery=Y&sort=rank&tab=default_tab&vid=book'

        rsp = requests.get(s, headers=self.headers)

        result = rsp.json()
        import json
        # formatted_rsp = json.dumps(result, indent=4, ensure_ascii=False)
        # print(formatted_rsp)
        return result


if __name__ == '__main__':
    client = LibSearchClient()
    client.search('python')
