import Alpine from "alpinejs";
import CTFd from "./index";
import { getOption } from "./utils/graphs/echarts/scoreboard";
import { embed } from "./utils/graphs/echarts";

window.Alpine = Alpine;
window.CTFd = CTFd;

// Default scoreboard polling interval to every 5 minutes
const scoreboardUpdateInterval = window.scoreboardUpdateInterval || 300000;

Alpine.data("ScoreboardDetail", () => ({
  data: {},
  show: true,
  activeBracket: null,

  async update() {
    this.data = await CTFd.pages.scoreboard.getScoreboardDetail(10, this.activeBracket);

    let optionMerge = window.scoreboardChartOptions;
    let option = getOption(CTFd.config.userMode, this.data, optionMerge);

    embed(this.$refs.scoregraph, option);
    this.show = Object.keys(this.data).length > 0;
  },

  async init() {
    this.update();

    setInterval(() => {
      this.update();
    }, scoreboardUpdateInterval);
  },
}));

// Helper functions for hybrid mode scoreboard API calls
const getHybridIndividualScoreboard = async () => {
  try {
    const response = await CTFd.fetch("/api/v1/scoreboard/individuals", {
      method: "GET",
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
    });
    const result = await response.json();
    return result.success ? result.data : [];
  } catch (error) {
    console.error("Error fetching individual scoreboard:", error);
    return [];
  }
};

const getHybridTeamScoreboard = async () => {
  try {
    const response = await CTFd.fetch("/api/v1/scoreboard/teams", {
      method: "GET",
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
    });
    const result = await response.json();
    return result.success ? result.data : [];
  } catch (error) {
    console.error("Error fetching team scoreboard:", error);
    return [];
  }
};

Alpine.data("ScoreboardList", () => ({
  standings: [],
  individualStandings: [],
  teamStandings: [],
  brackets: [],
  activeBracket: null,
  activeTab: 'individuals',
  isHybridMode: CTFd.config.userMode === 'hybrid',

  async update() {
    this.brackets = await CTFd.pages.scoreboard.getBrackets(CTFd.config.userMode);

    if (this.isHybridMode) {
      // In hybrid mode, fetch both individual and team standings
      this.individualStandings = await getHybridIndividualScoreboard();
      this.teamStandings = await getHybridTeamScoreboard();
    } else {
      // In standard mode, fetch regular standings
      this.standings = await CTFd.pages.scoreboard.getScoreboard();
    }
  },

  async init() {
    this.$watch("activeBracket", value => {
      this.$dispatch("bracket-change", value);
    });

    this.update();

    setInterval(() => {
      this.update();
    }, scoreboardUpdateInterval);
  },
}));

Alpine.start();
