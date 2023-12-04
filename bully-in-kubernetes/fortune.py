class FortuneCookieJar:
    """A class to fetch random fortunes (also based on categories)"""

    # Class variable, same for all instances
    VALID_CATEGORIES = ["all", "bible", "computers", "cookie", "definitions", "miscellaneous", "people", "platitudes", "politics", "science", "wisdom"]
    BASE_URL = "http://yerkee.com/api/fortune"

    def __init__(self, category="all"):
        self.__category = ""
        self.category = category
        self.__fortune = ""

    def __str__(self):
        return f"FortuneCookieJar instance with category: {self.__category}"
        
    @property
    def category(self):
        """Get the current category"""
        return self.__category
    
    @category.setter
    def category(self, value):
        """Set the category after validating it"""
        if value not in FortuneCookieJar.VALID_CATEGORIES:
            raise ValueError(f'{value} is not a valid category')
        self.__category = value

    def __update_fortune(self):
        """Fetch a new fortune based on the current category"""
        url = self.BASE_URL
        if self.__category != "all":
            url += f"/{self.__category}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            self.__fortune = response.json().get("fortune", "")
        except Exception as e:
            print(f"An exception was encountered: {e}")

    def get_random_fortune(self):
        """Get a random fortune"""
        self.__update_fortune()
        return self.__fortune