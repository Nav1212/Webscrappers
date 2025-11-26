#!/usr/bin/env python3
"""
Reddit Historical Scraper using Pushshift API

This script scrapes historical Reddit data using the Pushshift API and stores 
the content in a ZIP file with JSON format. The JSON hierarchy is:
subreddit -> post -> comments, with user information for posts and comments.
"""

import argparse
import json
import os
import time
import zipfile
from datetime import datetime, timedelta
from typing import Optional, List

import requests


class PushshiftRedditScraper:
    """Scrapes historical Reddit data using the Pushshift API."""

    # Pushshift API base URLs (using Pullpush.io which maintains Pushshift-compatible endpoints)
    PUSHSHIFT_SUBMISSIONS_URL = "https://api.pullpush.io/reddit/search/submission"
    PUSHSHIFT_COMMENTS_URL = "https://api.pullpush.io/reddit/search/comment"

    def __init__(self, rate_limit_delay: float = 1.0):
        """
        Initialize the scraper.

        Args:
            rate_limit_delay: Delay between API requests in seconds to avoid rate limiting.
        """
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "PushshiftRedditScraper/1.0"
        })

    def _make_request(self, url: str, params: dict) -> Optional[dict]:
        """
        Make a request to the Pushshift API with error handling.

        Args:
            url: The API endpoint URL.
            params: Query parameters for the request.

        Returns:
            JSON response data or None if request failed.
        """
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            time.sleep(self.rate_limit_delay)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            return None

    def fetch_submissions(
        self,
        subreddit: str,
        before: Optional[int] = None,
        after: Optional[int] = None,
        size: int = 100
    ) -> list:
        """
        Fetch submissions (posts) from a subreddit.

        Args:
            subreddit: Name of the subreddit to scrape.
            before: Unix timestamp - fetch posts before this time.
            after: Unix timestamp - fetch posts after this time.
            size: Number of posts to fetch (max 100 per request).

        Returns:
            List of submission dictionaries.
        """
        params = {
            "subreddit": subreddit,
            "size": min(size, 100),
            "sort": "desc",
            "sort_type": "created_utc"
        }

        if before is not None:
            params["before"] = before
        if after is not None:
            params["after"] = after

        data = self._make_request(self.PUSHSHIFT_SUBMISSIONS_URL, params)

        if data and "data" in data:
            return data["data"]
        return []

    def fetch_comments_for_post(self, post_id: str, size: int = 500) -> list:
        """
        Fetch comments for a specific post.

        Args:
            post_id: The Reddit post ID (without t3_ prefix).
            size: Maximum number of comments to fetch.

        Returns:
            List of comment dictionaries.
        """
        params = {
            "link_id": post_id,
            "size": min(size, 500),
            "sort": "desc",
            "sort_type": "created_utc"
        }

        data = self._make_request(self.PUSHSHIFT_COMMENTS_URL, params)

        if data and "data" in data:
            return data["data"]
        return []

    def format_submission(self, submission: dict) -> dict:
        """
        Format a submission into a structured dictionary with user info.

        Args:
            submission: Raw submission data from Pushshift.

        Returns:
            Formatted submission dictionary.
        """
        return {
            "id": submission.get("id"),
            "title": submission.get("title"),
            "selftext": submission.get("selftext", ""),
            "url": submission.get("url"),
            "score": submission.get("score"),
            "num_comments": submission.get("num_comments"),
            "created_utc": submission.get("created_utc"),
            "permalink": submission.get("permalink"),
            "user": {
                "username": submission.get("author"),
                "author_fullname": submission.get("author_fullname")
            },
            "comments": []
        }

    def format_comment(self, comment: dict) -> dict:
        """
        Format a comment into a structured dictionary with user info.

        Args:
            comment: Raw comment data from Pushshift.

        Returns:
            Formatted comment dictionary.
        """
        return {
            "id": comment.get("id"),
            "body": comment.get("body"),
            "score": comment.get("score"),
            "created_utc": comment.get("created_utc"),
            "parent_id": comment.get("parent_id"),
            "permalink": comment.get("permalink"),
            "user": {
                "username": comment.get("author"),
                "author_fullname": comment.get("author_fullname")
            }
        }

    def scrape_subreddit(
        self,
        subreddit: str,
        max_posts: int = 100,
        before: Optional[int] = None,
        after: Optional[int] = None,
        include_comments: bool = True
    ) -> dict:
        """
        Scrape a subreddit and return structured data.

        Args:
            subreddit: Name of the subreddit to scrape.
            max_posts: Maximum number of posts to scrape.
            before: Unix timestamp - fetch posts before this time.
            after: Unix timestamp - fetch posts after this time.
            include_comments: Whether to also fetch comments for each post.

        Returns:
            Dictionary with subreddit data in the required hierarchy.
        """
        print(f"Scraping subreddit: r/{subreddit}")

        subreddit_data = {
            "subreddit": subreddit,
            "scraped_at": datetime.utcnow().isoformat(),
            "posts": []
        }

        # Fetch submissions
        posts_fetched = 0
        current_before = before

        while posts_fetched < max_posts:
            batch_size = min(100, max_posts - posts_fetched)
            submissions = self.fetch_submissions(
                subreddit=subreddit,
                before=current_before,
                after=after,
                size=batch_size
            )

            if not submissions:
                break

            for submission in submissions:
                if posts_fetched >= max_posts:
                    break

                formatted_post = self.format_submission(submission)
                post_id = submission.get("id")

                # Fetch comments for this post if requested
                if include_comments and post_id:
                    print(f"  Fetching comments for post: {post_id}")
                    comments = self.fetch_comments_for_post(post_id)
                    formatted_post["comments"] = [
                        self.format_comment(c) for c in comments
                    ]

                subreddit_data["posts"].append(formatted_post)
                posts_fetched += 1

                # Update cursor for pagination
                if "created_utc" in submission:
                    current_before = submission["created_utc"]

            print(f"  Fetched {posts_fetched}/{max_posts} posts")

        return subreddit_data

    def scrape_multiple_subreddits(
        self,
        subreddits: list,
        max_posts_per_subreddit: int = 100,
        before: Optional[int] = None,
        after: Optional[int] = None,
        include_comments: bool = True
    ) -> dict:
        """
        Scrape multiple subreddits and return combined data.

        Args:
            subreddits: List of subreddit names to scrape.
            max_posts_per_subreddit: Maximum number of posts per subreddit.
            before: Unix timestamp - fetch posts before this time.
            after: Unix timestamp - fetch posts after this time.
            include_comments: Whether to also fetch comments for each post.

        Returns:
            Dictionary with all scraped data organized by subreddit.
        """
        result = {
            "metadata": {
                "scraped_at": datetime.utcnow().isoformat(),
                "total_subreddits": len(subreddits),
                "subreddits_list": subreddits
            },
            "subreddits": {}
        }

        for subreddit in subreddits:
            subreddit_data = self.scrape_subreddit(
                subreddit=subreddit,
                max_posts=max_posts_per_subreddit,
                before=before,
                after=after,
                include_comments=include_comments
            )
            result["subreddits"][subreddit] = subreddit_data

        return result

    def save_to_zip(self, data: dict, output_path: str) -> str:
        """
        Save scraped data to a ZIP file containing JSON.

        Args:
            data: The scraped data dictionary.
            output_path: Path for the output ZIP file.

        Returns:
            Path to the created ZIP file.
        """
        # Ensure the output path ends with .zip
        if not output_path.endswith('.zip'):
            output_path = output_path + '.zip'

        # Create directory if it doesn't exist
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        json_filename = os.path.basename(output_path).replace('.zip', '.json')

        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            json_content = json.dumps(data, indent=2, ensure_ascii=False)
            zipf.writestr(json_filename, json_content)

        print(f"Data saved to: {output_path}")
        return output_path

    def fetch_top_subreddits(self, limit: int = 1000) -> List[str]:
        """
        Fetch the top subreddits by subscriber count.
        
        Note: This uses a static list of popular subreddits since the Pushshift API
        doesn't provide subreddit rankings. In production, you might want to use
        Reddit's official API or maintain an updated list.

        Args:
            limit: Maximum number of subreddits to return.

        Returns:
            List of subreddit names.
        """
        # Top subreddits by subscriber count (as of 2024)
        # This is a curated list of popular subreddits
        top_subreddits = [
            "funny", "AskReddit", "gaming", "aww", "pics", "Music", "science",
            "worldnews", "videos", "movies", "todayilearned", "news", "Showerthoughts",
            "EarthPorn", "IAmA", "food", "gifs", "askscience", "Jokes", "LifeProTips",
            "explainlikeimfive", "Art", "books", "mildlyinteresting", "nottheonion",
            "DIY", "sports", "space", "gadgets", "television", "photoshopbattles",
            "Documentaries", "GetMotivated", "listentothis", "UpliftingNews", "tifu",
            "InternetIsBeautiful", "history", "philosophy", "announcements", "blog",
            "OldSchoolCool", "Futurology", "personalfinance", "WritingPrompts",
            "dataisbeautiful", "nostalgia", "creepy", "TwoXChromosomes", "technology",
            "WTF", "politics", "atheism", "bestof", "AdviceAnimals", "woahdude",
            "programming", "learnprogramming", "Python", "javascript", "webdev",
            "gamedev", "linux", "Android", "apple", "buildapc", "pcmasterrace",
            "Steam", "PS4", "PS5", "xboxone", "NintendoSwitch", "Games", "truegaming",
            "IndieGaming", "patientgamers", "GameDeals", "boardgames", "DnD",
            "wallpapers", "anime", "manga", "comics", "Marvel", "DC_Cinematic",
            "StarWars", "harrypotter", "LOTR", "gameofthrones", "breakingbad",
            "BetterCallSaul", "TheWire", "TheOffice", "PandR", "IASIP", "community",
            "brooklynninenine", "Sherlock", "DoctorWho", "startrek", "firefly",
            "Fantasy", "scifi", "horror", "Fitness", "loseit", "progresspics",
            "running", "bodyweightfitness", "nutrition", "MealPrepSunday", "recipes",
            "Cooking", "Baking", "AskCulinary", "cocktails", "Coffee", "tea",
            "beer", "wine", "whiskey", "travel", "solotravel", "backpacking",
            "camping", "hiking", "Outdoors", "climbing", "photography", "itookapicture",
            "photocritique", "analog", "postprocessing", "Cameras", "dogs", "cats",
            "Pets", "AnimalsBeingBros", "AnimalsBeingDerps", "NatureIsFuckingLit",
            "natureismetal", "WildlifePhotography", "birding", "Aquariums", "gardening",
            "houseplants", "succulents", "IndoorGarden", "landscaping", "woodworking",
            "metalworking", "Welding", "crafts", "knitting", "crochet", "sewing",
            "Leathercraft", "Pottery", "drawing", "painting", "DigitalArt", "PixelArt",
            "ArtFundamentals", "learnart", "SketchDaily", "Design", "graphic_design",
            "web_design", "UI_Design", "userexperience", "InteriorDesign", "RoomPorn",
            "CozyPlaces", "AmateurRoomPorn", "malelivingspace", "HomeImprovement",
            "HomeDecorating", "architecture", "ArchitecturePorn", "CityPorn",
            "InfrastructurePorn", "MapPorn", "dataisugly", "FellowKids", "CrappyDesign",
            "mildlyinfuriating", "oddlysatisfying", "Satisfyingasfuck", "Damnthatsinteresting",
            "BeAmazed", "interestingasfuck", "ThatsInsane", "nextfuckinglevel",
            "HumansBeingBros", "MadeMeSmile", "wholesomememes", "awwducational",
            "Eyebleach", "rarepuppers", "AnimalsBeingJerks", "StartledCats", "Zoomies",
            "tippytaps", "whatswrongwithyourdog", "blep", "teefies", "IllegallySmolCats",
            "Chonkers", "AbsoluteUnits", "curledfeetsies", "CatLoaf", "SupermodelCats",
            "CrossStitch", "quilting", "beadsprites", "origami", "papercraft",
            "3Dprinting", "maker", "arduino", "raspberry_pi", "electronics",
            "MechanicalKeyboards", "battlestations", "AverageBattlestations",
            "shittybattlestations", "retrogaming", "emulation", "gamecollecting",
            "vinyl", "audiophile", "headphones", "BudgetAudiophile", "hometheater",
            "htpc", "cordcutters", "Piracy", "DataHoarder", "selfhosted", "homelab",
            "sysadmin", "netsec", "cybersecurity", "hacking", "crypto", "CryptoCurrency",
            "Bitcoin", "ethereum", "wallstreetbets", "stocks", "investing", "options",
            "financialindependence", "povertyfinance", "Frugal", "EatCheapAndHealthy",
            "BuyItForLife", "zerowaste", "minimalism", "declutter", "konmari",
            "productivity", "getdisciplined", "DecidingToBeBetter", "selfimprovement",
            "socialskills", "confidence", "introvert", "Anxiety", "depression",
            "mentalhealth", "SuicideWatch", "offmychest", "TrueOffMyChest", "confession",
            "UnsentLetters", "relationships", "relationship_advice", "dating",
            "dating_advice", "Tinder", "OkCupid", "seduction", "socialanxiety",
            "lonely", "ForeverAlone", "MakeNewFriendsHere", "needafriend", "CasualConversation",
            "self", "AMA", "casualiama", "NoStupidQuestions", "OutOfTheLoop",
            "answers", "TooAfraidToAsk", "ExplainLikeImCalvin", "shittyaskscience",
            "askphilosophy", "AskHistorians", "AskSocialScience", "AskEngineers",
            "AskMen", "AskWomen", "AskMenOver30", "AskWomenOver30", "AskOldPeople",
            "AskParents", "AskDocs", "legaladvice", "bestoflegaladvice", "law",
            "AskLEO", "ProtectAndServe", "military", "army", "navy", "AirForce",
            "USMC", "Veterans", "JustBootThings", "Military_Finance", "MilitaryPorn",
            "CombatFootage", "WarCollege", "CredibleDefense", "LessCredibleDefence",
            "NonCredibleDefense", "geopolitics", "PoliticalDiscussion", "NeutralPolitics",
            "moderatepolitics", "PoliticalHumor", "Conservative", "Liberal", "Libertarian",
            "democrats", "Republican", "GreenParty", "socialism", "LateStageCapitalism",
            "capitalism", "Anarchism", "DebateCommunism", "DebateAnarchism",
            "changemyview", "unpopularopinion", "The10thDentist", "rant", "Vent",
            "TrueAskReddit", "DeepThoughts", "Showerthoughts", "Thoughts", "highdeas",
            "StonerThoughts", "trees", "eldertrees", "saplings", "vaporents", "CBD",
            "Drugs", "DrugNerds", "researchchemicals", "Psychonaut", "LSD",
            "shrooms", "DMT", "microdosing", "MDMA", "Nootropics", "StackAdvice",
            "Supplements", "Biohackers", "QuantifiedSelf", "Health", "medical",
            "medicine", "nursing", "pharmacy", "Dentistry", "optometry", "audiology",
            "physicaltherapy", "OccupationalTherapy", "slp", "MedicalSchool",
            "residency", "Premed", "MCAT", "Step1", "Physician", "Psychiatry",
            "psychology", "neuroscience", "cogsci", "BehavioralEconomics", "sociology",
            "Anthropology", "linguistics", "languagelearning", "duolingo", "French",
            "German", "Spanish", "Italian", "Portuguese", "Russian", "Japanese",
            "LearnJapanese", "Korean", "Chinese", "ChineseLanguage", "Arabic",
            "Hebrew", "Polish", "Dutch", "Swedish", "Norwegian", "Finnish", "Danish",
            "Greek", "Turkish", "Hindi", "Urdu", "Vietnamese", "Thai", "Indonesian",
            "Tagalog", "swahili", "translator", "TranslationStudies", "linguistics",
            "etymology", "logophilia", "WordAvalanches", "WordPorn", "words",
            "vocabulary", "grammar", "writing", "writingcirclejerk", "screenwriting",
            "Filmmakers", "VideoEditing", "videography", "cinematography", "colorists",
            "editors", "PostProcessing", "AfterEffects", "vfx", "MotionDesign",
            "Cinema4D", "blender", "Maya", "3dsmax", "ZBrush", "animation",
            "animationcareer", "storyboarding", "illustration", "ComicBookCollabs",
            "webcomics", "comicbooks", "DCcomics", "Marvel", "xmen", "batman",
            "superman", "spiderman", "marvelstudios", "MCUTheories", "FanTheories",
            "fixingmovies", "moviescirclejerk", "flicks", "TrueFilm", "criterion",
            "boutiquebluray", "dvdcollection", "HomeVideo", "4kbluray", "LaserDisc",
            "VHS", "ObscureMedia", "vintageads", "propagandaposters", "MoviePosterPorn",
            "AlbumArtPorn", "DesignPorn", "typography", "fonts", "identifythisfont",
            "Logo_Critique", "logodesign", "Infographics", "visualization", "chartporn",
            "mapporn", "papertowns", "imaginarymaps", "vexillology", "heraldry",
            "flags", "StateFlagRedesigns", "vexillologycirclejerk", "place",
            "place2017", "place2022", "rplace", "CoordinatedAttack", "placeatlas",
            "place_history", "placepride", "placehearts", "AmongUs", "RocketLeague",
            "leagueoflegends", "VALORANT", "Overwatch", "Overwatch2", "Hearthstone",
            "hearthstonecirclejerk", "competitivehs", "HSPulls", "customhearthstone",
            "wildhearthstone", "classicwow", "wow", "woweconomy", "wowguilds",
            "wownoob", "CompetitiveWoW", "WoWRolePlay", "warcraftlore", "warcraft3",
            "starcraft", "starcraft2", "AllThingsTerran", "allthingszerg", "allthingsprotoss",
            "Diablo", "diablo2", "diablo3", "diablo4", "Diablo2Resurrected",
            "PathOfExile", "pathofexilebuilds", "PoEBuilds", "GrimDawn", "LastEpoch",
            "Wolcen", "TorchIight", "Minecraft", "MinecraftMemes", "Minecraftbuilds",
            "MinecraftCommands", "feedthebeast", "Terraria", "starbound", "NoMansSkyTheGame",
            "EliteDangerous", "starcitizen", "SpaceEngineers", "Astroneer", "Subnautica",
            "subnautica_below_zero", "ARK", "playark", "ConanExiles", "valheim",
            "RimWorld", "RimWorldMods", "RimWorldArt", "SpaceCannibalism", "Kenshi",
            "dwarffortress", "factorio", "SatisfactoryGame", "shapezio", "mindustry",
            "Dyson_Sphere_Program", "OxygenNotIncluded", "prisonarchitect",
            "ProjectZomboid", "CivVI", "civ", "civ6", "civ5", "civ4", "civ3",
            "totalwar", "totalwarhammer", "humankind", "eu4", "CrusaderKings",
            "ck3", "hoi4", "victoria3", "Stellaris", "ParadoxPlaza",
            "ageofempires", "aoe4", "aoe2", "companyofheroes", "starcraft",
            "FalloutMods", "Fallout", "Fallout4", "Fallout76", "fo4", "fo76",
            "fnv", "NewVegasMemes", "ElderScrolls", "skyrim", "skyrimmods",
            "oblivion", "Morrowind", "elderscrollsonline", "TrueSTL", "teslore",
            "shittyteslore", "metalgearsolid", "DeathStranding", "NieRAutomataGame",
            "nier", "darksouls", "darksouls3", "DarkSouls2", "demonssouls",
            "bloodborne", "Eldenring", "Sekiro", "HollowKnight", "celestegame",
            "deadcells", "HadesTheGame", "slaythespire", "MonsterHunter", "MonsterHunterWorld",
            "MonsterHunterMeta", "MHRise", "MonsterHunterStories", "pokemon",
            "PokemonSwordAndShield", "PokemonLegendsArceus", "PokemonScarletViolet",
            "pokemongo", "TheSilphRoad", "pokemongodev", "ShinyPokemon", "nuzlocke",
            "pokemonmemes", "pokemon_competitive", "VGC", "PokemonTCG", "PkmnTCGCollections",
            "DigimonCardGame2020", "yugioh", "YuGiOhMasterDuel", "DuelLinks",
            "MagicArena", "mtg", "magicTCG", "EDH", "cEDH", "CompetitiveEDH",
            "ModernMagic", "Pauper", "mtglegacy", "mtgvintage", "mtgfinance",
            "mtgaltered", "custommagic", "BadMtgCombos", "mtgGore", "freemagic",
            "Warhammer", "Warhammer40k", "40kLore", "WarhammerCompetitive",
            "ageofsigmar", "WarhammerFantasy", "killteam", "MiddleEarthMiniatures",
            "minipainting", "Warhammer30k", "battletech", "BattleTechMods",
            "roguelikes", "roguelikedev", "roguelites", "IndieGaming", "incremental_games",
            "WebGames", "iosgaming", "AndroidGaming", "MobileGaming", "ShouldIbuythisgame",
            "GameRecommendations", "gamingsuggestions", "patientgamers", "truegaming",
            "Gaming4Gamers", "Games", "pcgaming", "pcmasterrace", "Steam",
            "SteamDeals", "GameDeals", "FreeGameFindings", "freegames", "giveaways",
            "RandomActsOfGaming", "GiftofGames", "BestOfAmazonPrime", "PlayStationPlus",
            "XboxGamePass", "NintendoSwitchDeals", "3DSdeals", "PS4Deals", "PS5restock",
            "hardwareswap", "buildapcsales", "bapcsalescanada", "buildapcuk",
            "buildmeapc", "buildapcforme", "PCBuilds", "laptops", "SuggestALaptop",
            "thinkpad", "chromeos", "chromebook", "mac", "macbookpro", "MacOS",
            "apple", "iphone", "ipad", "AppleWatch", "airpods", "ApplePay",
            "iOSBeta", "MacOSBeta", "shortcuts", "jailbreak", "sideloaded",
            "Android", "GooglePixel", "samsung", "galaxys10", "GalaxyS21",
            "GalaxyS22", "GalaxyNote9", "GalaxyFold", "oneplus", "Xiaomi",
            "Huawei", "Motorola", "Nokia", "LGphones", "LineageOS", "androidroot",
            "androidapps", "fossdroid", "androidthemes", "kustom", "androidwear",
            "WearOS", "GalaxyWatch", "AmazfitBip", "fitbit", "garmin", "Strava",
            "C25K", "running", "trailrunning", "ultramarathon", "marathon",
            "firstmarathon", "AdvancedRunning", "RunningWithDogs", "Runningmusic",
            "CrossCountry", "Sprinting", "trackandfield", "Rowing", "Swimming",
            "triathlon", "cycling", "bicycling", "MTB", "bikewrench", "whichbike",
            "bikecommuting", "FixedGearBicycle", "bmx", "unicycling", "skateboarding",
            "longboarding", "NewSkaters", "rollerblading", "rollerskating", "surfing",
            "bodyboarding", "scuba", "freediving", "snorkeling", "sailing", "boating",
            "kayaking", "canoeing", "Paddleboarding", "Whitewater", "jetski",
            "fishing", "Fishing_Gear", "flyfishing", "bassfishing", "kayakfishing",
            "IceFishing", "Spearfishing", "hunting", "Hunting_Gear", "bowhunting",
            "Archery", "airguns", "Shotguns", "longrange", "Revolvers", "CCW",
            "EDC", "flashlight", "knifeclub", "knives", "Bladesmith", "Blacksmith",
            "Metalworking", "Welding", "Machinists", "Skookum", "Tools", "handtools",
            "woodworking", "turning", "finishing", "BeginnerWoodWorking", "Workbenches",
            "ShopUpdates", "Workshop", "Garage", "garageporn", "Justrolledintotheshop",
            "MechanicAdvice", "Cartalk", "cars", "Autos", "spotted", "classiccars",
            "vintagecars", "projectcar", "Carporn", "BMW", "mercedes_benz", "Audi",
            "Volkswagen", "Porsche", "Ferrari", "Lamborghini", "AstonMartin",
            "McLaren", "Bentley", "RollsRoyce", "Maserati", "Jaguar", "LandRover",
            "Lexus", "Infiniti", "Acura", "Toyota", "Honda", "Nissan", "Mazda",
            "Subaru", "Mitsubishi", "Hyundai", "Kia", "Genesis", "Ford", "Chevrolet",
            "Dodge", "RAM_Trucks", "Jeep", "Tesla", "teslamotors", "TeslaModel3",
            "TeslaModelY", "TeslaLounge", "electricvehicles", "EV", "Rivian",
            "Lucid", "Polestar", "NIO", "F150Lightning", "Ioniq5", "Volt",
            "BoltEV", "Ioniq6", "ElectricScooters", "ElectricSkateboarding",
            "ebikes", "motorcycles", "motorcyclegear", "motorcyclelogistics",
            "Trackdays", "supermoto", "Harley", "Ducati", "KTM", "Triumph",
            "Kawasaki", "Yamaha", "Honda_Motorcycles", "suzuki", "IndianMotorcycle",
            "scooters", "Vespa", "Aviation", "flying", "Gliding", "Paragliding",
            "paramotors", "SkyDiving", "BASE", "hotairballooning", "Helicopters",
            "trains", "trainporn", "TrainPics", "TrainCrashSeries", "transit",
            "urbanplanning", "urbandesign", "fuckcars", "notjustbikes", "lowcar",
            "carfree", "walkablecities", "solarpunk", "collapse", "sustainability",
            "environment", "climate", "ClimateActionPlan", "ClimateOffensive",
            "ExtinctionRebellion", "Greta", "FridaysForFuture", "DeTrashed",
            "PlasticFreeLiving", "AntiConsumption", "NoCar", "BikePacking",
            "bicycletouring", "biketravel", "biketour",
            # Additional popular subreddits to reach 1000
            "Minecraft", "FortNiteBR", "apexlegends", "destiny2", "deadbydaylight",
            "Rainbow6", "Warframe", "GlobalOffensive", "dota2", "tf2",
            "GenshinImpact", "Genshin_Impact_Leaks", "HonkaiStarRail",
            "anime_irl", "wholesomeanimemes", "Animemes", "goodanimemes",
            "teenagers", "relationship_advice", "AmItheAsshole", "unpopularopinion",
            "Tinder", "antiwork", "WorkReform", "recruitinghell", "resumes",
            "jobs", "careerguidance", "cscareerquestions", "datascience",
            "MachineLearning", "artificial", "deeplearning", "learnmachinelearning"
        ]

        return top_subreddits[:limit]

    def fetch_top_posts_for_day(
        self,
        subreddit: str,
        date: datetime,
        limit: int = 10,
        include_comments: bool = True
    ) -> list:
        """
        Fetch the top posts for a specific day from a subreddit.

        Args:
            subreddit: Name of the subreddit.
            date: The date to fetch posts for.
            limit: Number of top posts to fetch.
            include_comments: Whether to fetch comments for each post.

        Returns:
            List of formatted post dictionaries sorted by score.
        """
        # Calculate start and end of day in UTC
        start_of_day = int(datetime(date.year, date.month, date.day).timestamp())
        end_of_day = start_of_day + 86400  # 24 hours in seconds

        params = {
            "subreddit": subreddit,
            "after": start_of_day,
            "before": end_of_day,
            "size": 100,  # Fetch more to get the top ones
            "sort": "desc",
            "sort_type": "score"
        }

        data = self._make_request(self.PUSHSHIFT_SUBMISSIONS_URL, params)

        if not data or "data" not in data:
            return []

        submissions = data["data"]

        # Sort by score and take top N
        submissions.sort(key=lambda x: x.get("score", 0), reverse=True)
        top_submissions = submissions[:limit]

        formatted_posts = []
        for submission in top_submissions:
            formatted_post = self.format_submission(submission)
            post_id = submission.get("id")

            if include_comments and post_id:
                comments = self.fetch_comments_for_post(post_id)
                formatted_post["comments"] = [
                    self.format_comment(c) for c in comments
                ]

            formatted_posts.append(formatted_post)

        return formatted_posts

    def scrape_daily_top_posts(
        self,
        subreddits: List[str],
        start_date: datetime,
        end_date: datetime,
        posts_per_day: int = 10,
        include_comments: bool = True,
        save_interval_days: int = 30,
        output_dir: str = "reddit_daily_data"
    ) -> dict:
        """
        Scrape top N posts per day from multiple subreddits over a date range.

        This method processes data in chunks and saves periodically to handle
        large date ranges and prevent data loss.

        Args:
            subreddits: List of subreddit names to scrape.
            start_date: Start date for scraping.
            end_date: End date for scraping.
            posts_per_day: Number of top posts to fetch per day per subreddit.
            include_comments: Whether to fetch comments for each post.
            save_interval_days: Save data to disk every N days.
            output_dir: Directory to save intermediate and final results.

        Returns:
            Dictionary with summary information about the scrape.
        """
        os.makedirs(output_dir, exist_ok=True)

        total_days = (end_date - start_date).days + 1
        total_subreddits = len(subreddits)

        print(f"Starting daily scrape:")
        print(f"  Subreddits: {total_subreddits}")
        print(f"  Date range: {start_date.date()} to {end_date.date()}")
        print(f"  Total days: {total_days}")
        print(f"  Posts per day per subreddit: {posts_per_day}")

        summary = {
            "metadata": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_subreddits": total_subreddits,
                "posts_per_day": posts_per_day,
                "scraped_at": datetime.utcnow().isoformat()
            },
            "files_created": [],
            "total_posts": 0,
            "total_comments": 0
        }

        current_date = start_date
        chunk_data = {"subreddits": {}}
        chunk_start_date = current_date
        days_in_chunk = 0

        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            print(f"\nProcessing date: {date_str}")

            for subreddit in subreddits:
                if subreddit not in chunk_data["subreddits"]:
                    chunk_data["subreddits"][subreddit] = {
                        "subreddit": subreddit,
                        "daily_posts": {}
                    }

                print(f"  Scraping r/{subreddit}...")
                posts = self.fetch_top_posts_for_day(
                    subreddit=subreddit,
                    date=current_date,
                    limit=posts_per_day,
                    include_comments=include_comments
                )

                chunk_data["subreddits"][subreddit]["daily_posts"][date_str] = posts
                summary["total_posts"] += len(posts)
                summary["total_comments"] += sum(
                    len(post.get("comments", [])) for post in posts
                )

            days_in_chunk += 1

            # Save chunk if interval reached or last day
            if days_in_chunk >= save_interval_days or current_date >= end_date:
                chunk_end_date = current_date
                filename = f"reddit_data_{chunk_start_date.strftime('%Y%m%d')}_to_{chunk_end_date.strftime('%Y%m%d')}.zip"
                filepath = os.path.join(output_dir, filename)

                chunk_data["metadata"] = {
                    "chunk_start_date": chunk_start_date.isoformat(),
                    "chunk_end_date": chunk_end_date.isoformat(),
                    "scraped_at": datetime.utcnow().isoformat()
                }

                self.save_to_zip(chunk_data, filepath)
                summary["files_created"].append(filepath)

                # Reset for next chunk
                chunk_data = {"subreddits": {}}
                chunk_start_date = current_date + timedelta(days=1)
                days_in_chunk = 0

            current_date += timedelta(days=1)

        print(f"\nScraping complete!")
        print(f"Total posts: {summary['total_posts']}")
        print(f"Total comments: {summary['total_comments']}")
        print(f"Files created: {len(summary['files_created'])}")

        # Save summary
        summary_path = os.path.join(output_dir, "scrape_summary.json")
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"Summary saved to: {summary_path}")

        return summary

    def scrape_top_subreddits_daily(
        self,
        num_subreddits: int = 1000,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        posts_per_day: int = 10,
        include_comments: bool = True,
        output_dir: str = "reddit_top_subreddits_data"
    ) -> dict:
        """
        Scrape top N posts per day from the top subreddits.

        This is a convenience method that combines fetching top subreddits
        and scraping daily posts.

        Args:
            num_subreddits: Number of top subreddits to scrape (max 1000).
            start_date: Start date (defaults to earliest available - 2005-06-23).
            end_date: End date (defaults to yesterday).
            posts_per_day: Number of top posts per day per subreddit.
            include_comments: Whether to fetch comments.
            output_dir: Directory to save results.

        Returns:
            Dictionary with scrape summary.
        """
        # Reddit was founded on June 23, 2005
        if start_date is None:
            start_date = datetime(2005, 6, 23)

        if end_date is None:
            end_date = datetime.utcnow() - timedelta(days=1)

        # Get top subreddits
        subreddits = self.fetch_top_subreddits(limit=num_subreddits)
        print(f"Fetched {len(subreddits)} top subreddits")

        return self.scrape_daily_top_posts(
            subreddits=subreddits,
            start_date=start_date,
            end_date=end_date,
            posts_per_day=posts_per_day,
            include_comments=include_comments,
            output_dir=output_dir
        )


def main():
    """Main function with subcommands for different scraping modes."""

    parser = argparse.ArgumentParser(
        description="Scrape historical Reddit data using Pushshift API"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Basic scrape command
    basic_parser = subparsers.add_parser(
        "scrape",
        help="Scrape posts from specified subreddits"
    )
    basic_parser.add_argument(
        "-s", "--subreddits",
        nargs="+",
        required=True,
        help="List of subreddits to scrape (without r/ prefix)"
    )
    basic_parser.add_argument(
        "-n", "--max-posts",
        type=int,
        default=10,
        help="Maximum number of posts per subreddit (default: 10)"
    )
    basic_parser.add_argument(
        "-o", "--output",
        default="reddit_data.zip",
        help="Output ZIP file path (default: reddit_data.zip)"
    )
    basic_parser.add_argument(
        "--before",
        type=int,
        default=None,
        help="Unix timestamp - fetch posts before this time"
    )
    basic_parser.add_argument(
        "--after",
        type=int,
        default=None,
        help="Unix timestamp - fetch posts after this time"
    )
    basic_parser.add_argument(
        "--no-comments",
        action="store_true",
        help="Skip fetching comments for posts"
    )
    basic_parser.add_argument(
        "--rate-limit",
        type=float,
        default=1.0,
        help="Delay between API requests in seconds (default: 1.0)"
    )

    # Daily top posts command
    daily_parser = subparsers.add_parser(
        "daily",
        help="Scrape top N posts per day from subreddits"
    )
    daily_parser.add_argument(
        "-s", "--subreddits",
        nargs="+",
        help="List of subreddits to scrape (if not using --top-subreddits)"
    )
    daily_parser.add_argument(
        "--top-subreddits",
        type=int,
        default=None,
        help="Use top N subreddits instead of specifying them (max 1000)"
    )
    daily_parser.add_argument(
        "-n", "--posts-per-day",
        type=int,
        default=10,
        help="Number of top posts per day per subreddit (default: 10)"
    )
    daily_parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Start date in YYYY-MM-DD format (default: 2005-06-23, Reddit founding)"
    )
    daily_parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="End date in YYYY-MM-DD format (default: yesterday)"
    )
    daily_parser.add_argument(
        "-o", "--output-dir",
        default="reddit_daily_data",
        help="Output directory for ZIP files (default: reddit_daily_data)"
    )
    daily_parser.add_argument(
        "--save-interval",
        type=int,
        default=30,
        help="Save data every N days (default: 30)"
    )
    daily_parser.add_argument(
        "--no-comments",
        action="store_true",
        help="Skip fetching comments for posts"
    )
    daily_parser.add_argument(
        "--rate-limit",
        type=float,
        default=1.0,
        help="Delay between API requests in seconds (default: 1.0)"
    )

    # List top subreddits command
    list_parser = subparsers.add_parser(
        "list-subreddits",
        help="List available top subreddits"
    )
    list_parser.add_argument(
        "-n", "--count",
        type=int,
        default=100,
        help="Number of subreddits to list (default: 100, max 1000)"
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    # Create scraper
    rate_limit = getattr(args, 'rate_limit', 1.0)
    scraper = PushshiftRedditScraper(rate_limit_delay=rate_limit)

    if args.command == "scrape":
        # Basic scrape mode
        data = scraper.scrape_multiple_subreddits(
            subreddits=args.subreddits,
            max_posts_per_subreddit=args.max_posts,
            before=args.before,
            after=args.after,
            include_comments=not args.no_comments
        )

        scraper.save_to_zip(data, args.output)

        total_posts = sum(
            len(sub_data.get("posts", []))
            for sub_data in data.get("subreddits", {}).values()
        )
        total_comments = sum(
            len(post.get("comments", []))
            for sub_data in data.get("subreddits", {}).values()
            for post in sub_data.get("posts", [])
        )

        print(f"\nScraping complete!")
        print(f"Total subreddits: {len(data.get('subreddits', {}))}")
        print(f"Total posts: {total_posts}")
        print(f"Total comments: {total_comments}")

    elif args.command == "daily":
        # Daily top posts mode
        if args.top_subreddits:
            subreddits = scraper.fetch_top_subreddits(limit=args.top_subreddits)
        elif args.subreddits:
            subreddits = args.subreddits
        else:
            print("Error: Either --subreddits or --top-subreddits is required")
            return

        # Parse dates
        if args.start_date:
            start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
        else:
            start_date = datetime(2005, 6, 23)  # Reddit founding date

        if args.end_date:
            end_date = datetime.strptime(args.end_date, "%Y-%m-%d")
        else:
            end_date = datetime.utcnow() - timedelta(days=1)

        scraper.scrape_daily_top_posts(
            subreddits=subreddits,
            start_date=start_date,
            end_date=end_date,
            posts_per_day=args.posts_per_day,
            include_comments=not args.no_comments,
            save_interval_days=args.save_interval,
            output_dir=args.output_dir
        )

    elif args.command == "list-subreddits":
        subreddits = scraper.fetch_top_subreddits(limit=args.count)
        print(f"Top {len(subreddits)} subreddits:")
        for i, sub in enumerate(subreddits, 1):
            print(f"  {i}. r/{sub}")


if __name__ == "__main__":
    main()
