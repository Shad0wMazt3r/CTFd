import "./main";
import CTFd from "../compat/CTFd";
import $ from "jquery";
import "../compat/json";
import { ezAlert } from "../compat/ezq";

const api_func = {
  users: (x, y) => CTFd.api.patch_user_public({ userId: x }, y),
  teams: (x, y) => CTFd.api.patch_team_public({ teamId: x }, y),
};

function toggleAccount() {
  const $btn = $(this);
  const id = $btn.data("account-id");
  const state = $btn.data("state");
  let hidden = undefined;
  if (state === "visible") {
    hidden = true;
  } else if (state === "hidden") {
    hidden = false;
  }

  const params = {
    hidden: hidden,
  };

  // In hybrid mode, determine if this is a user or team based on the context
  let apiFunction;
  if (CTFd.config.userMode === 'hybrid') {
    // Check if this element has a user-id data attribute (indicates individual user)
    const userId = $btn.data("user-id");
    if (userId) {
      apiFunction = api_func.users;
    } else {
      // Otherwise, it's a team
      apiFunction = api_func.teams;
    }
  } else {
    // Standard mode - use the configured user mode
    apiFunction = api_func[CTFd.config.userMode];
  }

  apiFunction(id, params).then((response) => {
    if (response.success) {
      if (hidden) {
        $btn.data("state", "hidden");
        $btn.addClass("btn-danger").removeClass("btn-success");
        $btn.text("Hidden");
      } else {
        $btn.data("state", "visible");
        $btn.addClass("btn-success").removeClass("btn-danger");
        $btn.text("Visible");
      }
    }
  });
}

function toggleSelectedAccounts(selectedAccounts, action) {
  const params = {
    hidden: action === "hidden" ? true : false,
  };
  const reqs = [];
  
  // Handle hybrid mode separately
  if (CTFd.config.userMode === 'hybrid') {
    // In hybrid mode, accounts can be either individual users or teams
    for (let accId of selectedAccounts.accounts) {
      reqs.push(api_func.teams(accId, params));  // Team accounts
    }
    for (let userId of selectedAccounts.users) {
      reqs.push(api_func.users(userId, params));  // Individual user accounts
    }
  } else {
    // Standard mode
    for (let accId of selectedAccounts.accounts) {
      reqs.push(api_func[CTFd.config.userMode](accId, params));
    }
    for (let accId of selectedAccounts.users) {
      reqs.push(api_func["users"](accId, params));
    }
  }
  
  Promise.all(reqs).then((_responses) => {
    window.location.reload();
  });
}

function bulkToggleAccounts(_event) {
  // Get selected account and user IDs but only on the active tab.
  // Technically this could work for both tabs at the same time but that seems like
  // bad behavior. We don't want to accidentally unhide a user/team accidentally
  let accountIDs = $(".tab-pane.active input[data-account-id]:checked").map(
    function () {
      return $(this).data("account-id");
    },
  );

  let userIDs = $(".tab-pane.active input[data-user-id]:checked").map(
    function () {
      return $(this).data("user-id");
    },
  );

  let selectedUsers = {
    accounts: accountIDs,
    users: userIDs,
  };

  ezAlert({
    title: "Toggle Visibility",
    body: $(`
    <form id="scoreboard-bulk-edit">
      <div class="form-group">
        <label>Visibility</label>
        <select name="visibility" data-initial="">
          <option value="">--</option>
          <option value="visible">Visible</option>
          <option value="hidden">Hidden</option>
        </select>
      </div>
    </form>
    `),
    button: "Submit",
    success: function () {
      let data = $("#scoreboard-bulk-edit").serializeJSON(true);
      let state = data.visibility;
      toggleSelectedAccounts(selectedUsers, state);
    },
  });
}

$(() => {
  $(".scoreboard-toggle").click(toggleAccount);
  $("#scoreboard-edit-button").click(bulkToggleAccounts);
  
  // Handle bulk selectors for hybrid mode tables
  $("#individual-scoreboard-bulk-select").change(function() {
    const isChecked = $(this).prop('checked');
    $("#individual-scoreboard input[type=checkbox]").prop('checked', isChecked);
  });
  
  $("#team-scoreboard-bulk-select").change(function() {
    const isChecked = $(this).prop('checked');
    $("#team-scoreboard input[type=checkbox]").prop('checked', isChecked);
  });
});
